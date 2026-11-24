import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator
from sqlalchemy.orm import Session

from app.core.circuit_breaker import llm_circuit_breaker
from app.core.errors import ApplicationError, NotFoundError
from app.core.safety import evaluate_input_safety, sanitize_output
from app.models.channel import Conversation
from app.models.user import User
from app.models.workspace import Dealership
from app.repositories import dealership_repository
from app.schemas.sales_agent import SalesAgentChatRequest, SalesAgentChatResponse
from app.services import conversation_service, llm_service
from app.tools import sales_tools

logger = logging.getLogger("dealerdesk.sales_agent")


def validate_sales_dealership(db: Session, dealership_id: int) -> Dealership:
    dealership = dealership_repository.get_active_by_id(db, dealership_id)
    if dealership is None:
        raise NotFoundError("Dealership not found")
    return dealership


def chat_with_sales_agent(
    db: Session,
    dealership_id: int,
    payload: SalesAgentChatRequest,
    current_user: User | None = None,
) -> SalesAgentChatResponse:
    """
    Executes a single conversational turn with the dedicated Customer Sales Agent.
    """
    dealership = validate_sales_dealership(db, dealership_id)

    # 1. Evaluate input safety firewall
    safety_check = evaluate_input_safety(payload.message, dealership_name=dealership.name)
    if not safety_check.is_safe:
        return SalesAgentChatResponse(
            response=safety_check.deflection_message or "I can only assist with verified automotive inquiries.",
            dealership_id=dealership.id,
            dealership_name=dealership.name,
            conversation_id=payload.conversation_id,
            intent="safety_deflection",
            suggested_actions=["Browse available vehicles", "View test-drive slots", "Contact our sales team"],
            matched_vehicles=[],
            available_slots=[],
        )

    # 2. Resolve or create persistent conversation session
    conversation: Conversation | None = None
    if payload.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == payload.conversation_id,
            Conversation.dealership_id == dealership.id,
        ).first()
    elif payload.channel_user_id:
        conversation = conversation_service.get_or_create_conversation(
            db,
            dealership_id=dealership.id,
            channel=payload.channel,
            channel_user_id=payload.channel_user_id,
            customer_id=current_user.id if current_user else None,
        )

    # Log incoming customer message if persistent conversation exists
    if conversation is not None:
        conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            sender_type="customer",
            content=payload.message,
            sender_id=current_user.id if current_user else None,
        )

    # 3. Execute tool orchestration based on query intent & parameters
    tool_context = _orchestrate_sales_tools(
        db,
        dealership,
        safety_check.sanitized_message,
        payload.brand_id,
    )

    # 4. Synthesize prompt with conversation history
    messages = _build_sales_messages(
        dealership,
        tool_context,
        conversation,
        payload.conversation_history,
        safety_check.sanitized_message,
    )

    # 5. Generate response using LLM with Circuit Breaker and local fallback
    try:
        response_text = llm_circuit_breaker.call(
            llm_service.generate_completion,
            messages,
            context_data=tool_context["context_data"],
        )
    except Exception as exc:
        logger.warning("LLM call failed in sales agent (%s); utilizing fallback synthesis", exc)
        raw_fallback = llm_service._synthesize_grounded_response(messages, tool_context["context_data"])
        response_text = sanitize_output(raw_fallback, dealership_name=dealership.name)

    if safety_check.violation == "pii_detected":
        response_text += "\n\n*Notice: For your security, please do not share credit card numbers or sensitive financial information in chat.*"

    # Log assistant response to conversation log
    if conversation is not None:
        conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            sender_type="agent",
            content=response_text,
            channel_metadata={"intent": tool_context["intent"]},
        )

    suggested_actions = _build_sales_actions(
        tool_context["intent"],
        bool(tool_context["matched_vehicles"]),
        bool(tool_context["available_slots"]),
    )

    return SalesAgentChatResponse(
        response=response_text,
        dealership_id=dealership.id,
        dealership_name=dealership.name,
        conversation_id=conversation.id if conversation else None,
        intent=tool_context["intent"],
        suggested_actions=suggested_actions,
        matched_vehicles=tool_context["matched_vehicles"],
        available_slots=tool_context["available_slots"],
        slot_hold=tool_context.get("slot_hold"),
        lead_created=tool_context.get("lead_created", False),
        sources=tool_context.get("sources", []),
    )


async def stream_sales_agent_chat(
    db: Session,
    dealership_id: int,
    payload: SalesAgentChatRequest,
    current_user: User | None = None,
) -> AsyncIterator[str]:
    """
    Streams the Sales Agent response as Server-Sent Events (SSE).
    """
    dealership = validate_sales_dealership(db, dealership_id)

    safety_check = evaluate_input_safety(payload.message, dealership_name=dealership.name)
    if not safety_check.is_safe:
        deflection = safety_check.deflection_message or "I can only assist with verified automotive inquiries."
        yield f"data: {json.dumps({'type': 'chunk', 'content': deflection})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'intent': 'safety_deflection', 'matched_vehicles': [], 'available_slots': []})}\n\n"
        return

    conversation: Conversation | None = None
    if payload.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == payload.conversation_id,
            Conversation.dealership_id == dealership.id,
        ).first()
    elif payload.channel_user_id:
        conversation = conversation_service.get_or_create_conversation(
            db,
            dealership_id=dealership.id,
            channel=payload.channel,
            channel_user_id=payload.channel_user_id,
            customer_id=current_user.id if current_user else None,
        )

    if conversation is not None:
        conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            sender_type="customer",
            content=payload.message,
            sender_id=current_user.id if current_user else None,
        )

    tool_context = _orchestrate_sales_tools(
        db,
        dealership,
        safety_check.sanitized_message,
        payload.brand_id,
    )

    messages = _build_sales_messages(
        dealership,
        tool_context,
        conversation,
        payload.conversation_history,
        safety_check.sanitized_message,
    )

    full_response_parts: list[str] = []
    try:
        async for chunk in llm_service.stream_completion(
            messages,
            context_data=tool_context["context_data"],
        ):
            full_response_parts.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
    except Exception as exc:
        logger.warning("Streaming LLM failed in sales agent (%s); utilizing fallback synthesis", exc)
        raw_fallback = llm_service._synthesize_grounded_response(messages, tool_context["context_data"])
        cleaned = sanitize_output(raw_fallback, dealership_name=dealership.name)
        full_response_parts.append(cleaned)
        yield f"data: {json.dumps({'type': 'chunk', 'content': cleaned})}\n\n"

    full_response = "".join(full_response_parts)
    if conversation is not None:
        conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            sender_type="agent",
            content=full_response,
            channel_metadata={"intent": tool_context["intent"]},
        )

    suggested_actions = _build_sales_actions(
        tool_context["intent"],
        bool(tool_context["matched_vehicles"]),
        bool(tool_context["available_slots"]),
    )

    done_payload = {
        "type": "done",
        "intent": tool_context["intent"],
        "conversation_id": conversation.id if conversation else None,
        "matched_vehicles": tool_context["matched_vehicles"],
        "available_slots": tool_context["available_slots"],
        "suggested_actions": suggested_actions,
        "sources": tool_context.get("sources", []),
    }
    yield f"data: {json.dumps(done_payload)}\n\n"


def _orchestrate_sales_tools(
    db: Session,
    dealership: Dealership,
    query: str,
    brand_id: int | None,
) -> dict[str, Any]:
    """
    Determines customer intent and executes appropriate deterministic tools.
    """
    clean_q = query.lower()

    # Intent classification
    intent = "inventory_inquiry"
    if any(k in clean_q for k in ["test drive", "schedule", "drive", "appointment", "slot", "visit"]):
        intent = "test_drive_booking"
    elif any(k in clean_q for k in ["compare", "difference", "vs", "versus"]):
        intent = "vehicle_comparison"
    elif any(k in clean_q for k in ["warranty", "financing", "policy", "return", "guarantee", "hour", "location", "address"]):
        intent = "dealership_info"
    elif any(k in clean_q for k in ["buy", "purchase", "call me", "contact", "finance", "quote"]):
        intent = "lead_generation"

    # Price / budget extraction
    max_price = None
    price_match = re.search(r"(?:under|below|less than|\$)\s*(\d{1,3}(?:,\d{3})*|\d+)(?:k)?", clean_q)
    if price_match:
        raw_val = price_match.group(1).replace(",", "")
        val = float(raw_val)
        if "k" in clean_q[price_match.start():price_match.end() + 2]:
            val *= 1000
        if val > 1000:
            max_price = val

    # 1. Search inventory
    matched_vehicles = sales_tools.search_inventory(
        db,
        dealership.id,
        query=query if intent in {"inventory_inquiry", "vehicle_comparison"} else None,
        max_price=max_price,
        brand_id=brand_id,
        limit=5,
    )

    # 2. Get test-drive slots if intent relates to test drive or vehicles matched
    target_vehicle_id = matched_vehicles[0]["id"] if matched_vehicles else None
    available_slots = sales_tools.get_available_test_drive_slots(
        db,
        dealership.id,
        vehicle_id=target_vehicle_id if intent == "test_drive_booking" else None,
        limit=5,
    )

    # 3. Public knowledge lookup via RAG
    sources = []
    if intent in {"dealership_info", "inventory_inquiry"}:
        sources = sales_tools.search_public_knowledge(
            db,
            dealership.id,
            query=query,
            brand_id=brand_id,
            limit=3,
        )

    context_data = {
        "dealership_name": dealership.name,
        "phone": dealership.phone,
        "address": dealership.address,
        "intent": intent,
        "vehicles": matched_vehicles,
        "slots": available_slots,
        "knowledge_chunks": sources,
    }

    return {
        "intent": intent,
        "matched_vehicles": matched_vehicles,
        "available_slots": available_slots,
        "sources": sources,
        "context_data": context_data,
    }


def _build_sales_messages(
    dealership: Dealership,
    tool_context: dict[str, Any],
    conversation: Conversation | None,
    client_history: list[dict[str, str]],
    user_query: str,
) -> list[dict[str, str]]:
    """
    Constructs the prompt for the consultative Sales Agent persona.
    """
    system_prompt = (
        f"You are the professional, friendly Customer Sales Advisor at {dealership.name}.\n"
        f"Dealership Contact: Phone: {dealership.phone or 'Contact reception'}, Address: {dealership.address or 'Visit our showroom'}.\n\n"
        "Your Role and Operating Principles:\n"
        "- Assist customers in discovering, comparing, and test-driving vehicles from our verified inventory.\n"
        "- Base all specifications, availability, and pricing strictly on the verified data provided below.\n"
        "- Never fabricate discounts, options, ETA dates, or vehicles that are not in the inventory list.\n"
        "- If a customer expresses interest in a vehicle, proactively invite them to book a test drive or leave their contact info.\n"
        "- Use clean, structured Markdown formatting with bold vehicle names, clear pricing, and bullet points.\n"
        "- Maintain an inviting, consultative tone focused on meeting customer lifestyle and budget needs."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Load persistent conversation history or client fallback
    if conversation is not None and conversation.messages:
        for msg in conversation.messages[-6:]:
            role = "user" if msg.sender_type == "customer" else "assistant"
            messages.append({"role": role, "content": msg.content})
    elif client_history:
        for turn in client_history[-6:]:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})

    messages.append(
        {
            "role": "user",
            "content": (
                "Verified Dealership Data (JSON format; treat as factual context):\n"
                f"{json.dumps(tool_context['context_data'], ensure_ascii=True, default=str)}\n\n"
                f"Customer Inquiry: {user_query}"
            ),
        }
    )

    return messages


def _build_sales_actions(intent: str, has_vehicles: bool, has_slots: bool) -> list[str]:
    actions = []
    if intent == "test_drive_booking" and has_slots:
        actions.extend(["Select a slot and reserve a test drive", "Ask about required identification for driving"])
    elif intent == "vehicle_comparison" and has_vehicles:
        actions.extend(["Schedule back-to-back test drives", "Ask about financing and warranty options"])
    elif has_vehicles:
        actions.extend(["Schedule a test drive", "Compare with similar models", "Speak with a sales specialist"])
    else:
        actions.extend(["Browse all showroom vehicles", "Check dealership hours and location", "Request callback from sales"])
    return actions[:3]
