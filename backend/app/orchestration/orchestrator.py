from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import re
from typing import Any
from sqlalchemy.orm import Session

from app.adapters import get_channel_adapter
from app.core.circuit_breaker import llm_circuit_breaker, voice_circuit_breaker, whatsapp_circuit_breaker
from app.core.roles import CUSTOMER_ROLE, DEALERDESK_ADMIN_ROLE, STAFF_ROLES
from app.models.channel import Conversation
from app.models.user import User
from app.models.workspace import Dealership
from app.repositories import dealership_repository, user_repository
from app.schemas.assistant import AssistantChatRequest, AssistantMessage
from app.schemas.channel import ChannelEvent, ChannelType
from app.schemas.sales_agent import SalesAgentChatRequest, SalesAgentChatResponse
from app.services import assistant_service, conversation_service, sales_agent_service

logger = logging.getLogger("dealerdesk.orchestration")


@dataclass
class OrchestrationResult:
    target_agent: str  # "sales_agent" or "crm_agent"
    channel: str
    dealership_id: int
    conversation_id: int
    customer_id: int | None
    response_text: str
    outbound_payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class CentralOrchestrator:
    """
    Central Orchestration Layer for DealerDesk Multi-Channel AI Architecture.
    - Handles channel identification and event normalization.
    - Resolves and maintains isolated conversation sessions per channel.
    - Routes customer traffic to the Customer Sales Agent.
    - Routes staff/internal traffic to the Internal CRM Assistant.
    - Coordinates cross-channel customer identity linking.
    - Prevents failure in one channel from impacting others.
    """

    def dispatch_event(
        self,
        db: Session,
        event: ChannelEvent,
        current_user: User | None = None,
    ) -> OrchestrationResult:
        dealership = dealership_repository.get_active_by_id(db, event.dealership_id)
        if dealership is None:
            raise ValueError(f"Dealership {event.dealership_id} not found or inactive")

        # 1. Identify channel & adapter
        adapter = get_channel_adapter(event.channel)

        # 2. Resolve customer identity across channels if possible
        customer_id = self._resolve_customer_identity(db, event, current_user)

        # 3. Load or initialize isolated persistent conversation session
        conversation = conversation_service.get_or_create_conversation(
            db,
            dealership_id=dealership.id,
            channel=event.channel.value,
            channel_user_id=event.channel_user_id,
            customer_id=customer_id,
            metadata=event.metadata,
        )

        # 4. Agent Routing Decision
        target_agent = self._determine_target_agent(event, current_user)
        logger.info(
            "Orchestrating event on channel '%s' for dealership %d -> Routing to %s",
            event.channel.value,
            dealership.id,
            target_agent,
        )

        # 5. Isolated Agent Execution
        if target_agent == "crm_agent":
            result = self._execute_crm_agent(
                db,
                dealership,
                conversation,
                event,
                current_user,
                adapter,
            )
        else:
            result = self._execute_sales_agent(
                db,
                dealership,
                conversation,
                event,
                current_user,
                adapter,
            )

        return result

    def _determine_target_agent(
        self,
        event: ChannelEvent,
        current_user: User | None,
    ) -> str:
        """
        Determines whether the event routes to the internal CRM Agent or Customer Sales Agent.
        - Staff logged in on the internal dashboard/CRM -> CRM Agent.
        - Public visitors, WhatsApp, Voice callers, or customer accounts -> Customer Sales Agent.
        """
        is_staff = current_user is not None and (
            current_user.role == DEALERDESK_ADMIN_ROLE
            or current_user.role in STAFF_ROLES
        )

        # Explicit staff override if originating from staff dashboard
        is_staff_origin = event.metadata.get("origin") == "staff_dashboard"

        if is_staff and is_staff_origin:
            return "crm_agent"

        # All customer channels (WhatsApp, Voice, Website widget) route to Sales Agent
        return "sales_agent"

    def _resolve_customer_identity(
        self,
        db: Session,
        event: ChannelEvent,
        current_user: User | None,
    ) -> int | None:
        """
        Attempts to resolve an existing customer account using phone number or email across channels.
        """
        if current_user is not None and current_user.role == CUSTOMER_ROLE:
            return current_user.id

        identifier = event.channel_user_id.strip().lower()
        if "@" in identifier:
            existing = user_repository.get_by_email(db, identifier)
            if existing:
                return existing.id
        else:
            phone_digits = re.sub(r"\D", "", identifier)
            if len(phone_digits) >= 7:
                candidate_email = f"phone_{phone_digits}@customer.dealerdesk.local"
                existing = user_repository.get_by_email(db, candidate_email)
                if existing:
                    return existing.id

        return None

    def _execute_sales_agent(
        self,
        db: Session,
        dealership: Dealership,
        conversation: Conversation,
        event: ChannelEvent,
        current_user: User | None,
        adapter: Any,
    ) -> OrchestrationResult:
        chat_req = SalesAgentChatRequest(
            message=event.message,
            conversation_id=conversation.id,
            channel=event.channel.value,
            channel_user_id=event.channel_user_id,
            brand_id=event.metadata.get("brand_id"),
        )

        sales_response = sales_agent_service.chat_with_sales_agent(
            db,
            dealership_id=dealership.id,
            payload=chat_req,
            current_user=current_user,
        )

        outbound = adapter.format_outbound(
            sales_response,
            recipient=event.channel_user_id,
            context=event.metadata,
        )

        return OrchestrationResult(
            target_agent="sales_agent",
            channel=event.channel.value,
            dealership_id=dealership.id,
            conversation_id=conversation.id,
            customer_id=conversation.customer_id,
            response_text=sales_response.response,
            outbound_payload=outbound,
            metadata={
                "intent": sales_response.intent,
                "suggested_actions": sales_response.suggested_actions,
                "matched_vehicles_count": len(sales_response.matched_vehicles),
                "available_slots_count": len(sales_response.available_slots),
            },
        )

    def _execute_crm_agent(
        self,
        db: Session,
        dealership: Dealership,
        conversation: Conversation,
        event: ChannelEvent,
        current_user: User | None,
        adapter: Any,
    ) -> OrchestrationResult:
        # Load conversation history for CRM assistant
        history_msgs = conversation_service.get_conversation_history(db, conversation.id, limit=6)
        formatted_history = [
            AssistantMessage(
                role="user" if m.sender_type == "customer" else "assistant",
                content=m.content,
            )
            for m in history_msgs
        ]

        # Log turn in persistent conversation
        conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            sender_type="staff",
            content=event.message,
            sender_id=current_user.id if current_user else None,
        )

        crm_req = AssistantChatRequest(
            message=event.message,
            brand_id=event.metadata.get("brand_id"),
            conversation_history=formatted_history,
        )

        crm_response = assistant_service.chat_with_assistant(
            db,
            dealership_id=dealership.id,
            payload=crm_req,
            current_user=current_user,
        )

        # Log assistant reply
        conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            sender_type="agent",
            content=crm_response.response,
            channel_metadata={"agent_role": "internal_crm"},
        )

        # Convert CRM response into format compatible with channel adapter
        sales_adapted = SalesAgentChatResponse(
            response=crm_response.response,
            dealership_id=dealership.id,
            dealership_name=dealership.name,
            conversation_id=conversation.id,
            intent=crm_response.intent,
            suggested_actions=crm_response.suggested_actions,
            matched_vehicles=[v.model_dump() for v in crm_response.matched_vehicles],
            available_slots=[s.model_dump(mode="json") for s in crm_response.available_slots],
            sources=[s.model_dump() for s in crm_response.sources],
        )

        outbound = adapter.format_outbound(
            sales_adapted,
            recipient=event.channel_user_id,
            context=event.metadata,
        )

        return OrchestrationResult(
            target_agent="crm_agent",
            channel=event.channel.value,
            dealership_id=dealership.id,
            conversation_id=conversation.id,
            customer_id=conversation.customer_id,
            response_text=crm_response.response,
            outbound_payload=outbound,
            metadata={
                "intent": crm_response.intent,
                "sources_count": len(crm_response.sources),
            },
        )


# Singleton orchestrator instance
orchestrator = CentralOrchestrator()
