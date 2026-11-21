from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.user import User
from app.repositories import dealership_repository, test_drive_repository, vehicle_repository
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantSlotMatch,
    AssistantSource,
    AssistantVehicleMatch,
)
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services import knowledge_service, llm_service


def chat_with_assistant(
    db: Session,
    dealership_id: int,
    payload: AssistantChatRequest,
    current_user: User | None = None,
) -> AssistantChatResponse:
    dealership = dealership_repository.get_active_by_id(db, dealership_id)
    if dealership is None:
        raise NotFoundError("Dealership not found")

    settings = test_drive_repository.get_settings(db, dealership_id)
    business_hours = (
        f"{settings.opening_time} to {settings.closing_time}"
        if settings
        else "09:00 to 17:00"
    )

    user_query = payload.message.strip().lower()
    intent = _classify_intent(user_query)

    # 1. Retrieve dealership inventory
    eligible_vehicles = vehicle_repository.list_for_dealership(
        db,
        dealership_id,
        include_archived_brands=False,
    )
    if payload.brand_id is not None:
        eligible_vehicles = [v for v in eligible_vehicles if v.brand_id == payload.brand_id]
    matched_vehicles = [
        AssistantVehicleMatch(
            id=v.id,
            make=v.make,
            model=v.model,
            model_year=v.model_year,
            price=v.price,
            stock_number=v.stock_number,
            test_drive_enabled=v.test_drive_enabled,
            is_available=v.is_available,
        )
        for v in eligible_vehicles
        if v.is_available
    ]

    # Filter vehicles if user mentioned specific terms
    if any(v.model.lower() in user_query or v.make.lower() in user_query for v in matched_vehicles):
        matched_vehicles = [
            v for v in matched_vehicles
            if v.model.lower() in user_query or v.make.lower() in user_query
        ]

    # 2. Retrieve available test-drive slots
    raw_slots = test_drive_repository.list_slots(
        db,
        dealership_id,
        available_only=True,
    )
    now = datetime.now(timezone.utc)
    available_slots = [
        AssistantSlotMatch(
            id=s.id,
            vehicle_id=s.vehicle_id,
            starts_at=s.starts_at,
            ends_at=s.ends_at,
            remaining_capacity=max(0, s.capacity - s.booked_count),
        )
        for s in raw_slots
        if s.is_active and s.starts_at > now and s.booked_count < s.capacity
    ][:5]

    # 3. Retrieve knowledge chunks via RAG
    knowledge_sources: list[AssistantSource] = []
    try:
        search_res = knowledge_service.search(
            db,
            dealership_id,
            KnowledgeSearchRequest(
                query=payload.message,
                brand_id=payload.brand_id,
                limit=3,
            ),
        )
        for r in search_res:
            knowledge_sources.append(
                AssistantSource(
                    document_id=r.document_id,
                    filename=r.filename,
                    page_number=r.page_number,
                    snippet=r.content,
                    score=r.score,
                )
            )
    except Exception:
        pass

    # 4. Build context dictionary
    context_data: dict[str, Any] = {
        "dealership_name": dealership.name,
        "address": dealership.address or "the main dealership office",
        "phone": dealership.phone or "our contact line",
        "business_hours": business_hours,
        "intent": intent,
        "vehicles": [v.model_dump() for v in matched_vehicles],
        "slots": [
            {
                "id": s.id,
                "starts_at": s.starts_at.isoformat(),
                "ends_at": s.ends_at.isoformat(),
                "remaining_capacity": s.remaining_capacity,
            }
            for s in available_slots
        ],
        "knowledge_chunks": [k.model_dump() for k in knowledge_sources],
    }

    # 5. Build prompt messages
    system_prompt = (
        f"You are the official dealership AI assistant for {dealership.name}.\n"
        f"Operating hours: {business_hours}. Address: {dealership.address}.\n"
        "Guidelines:\n"
        "- Base answers ONLY on the provided dealership catalog, test-drive slots, and official knowledge base.\n"
        "- Never hallucinate vehicles, prices, or policies not present in the data.\n"
        "- If the customer asks for a test drive, guide them to the available slots.\n"
        "- Be professional, friendly, and concise."
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in payload.conversation_history[-6:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": payload.message})

    # 6. Generate AI response
    response_text = llm_service.generate_completion(messages, context_data=context_data)

    suggested_actions = _build_suggested_actions(intent, bool(matched_vehicles), bool(available_slots))

    return AssistantChatResponse(
        response=response_text,
        dealership_id=dealership.id,
        dealership_name=dealership.name,
        brand_id=payload.brand_id,
        intent=intent,
        sources=knowledge_sources,
        matched_vehicles=matched_vehicles[:5],
        available_slots=available_slots,
        suggested_actions=suggested_actions,
    )


def _classify_intent(query: str) -> str:
    if any(k in query for k in ["human", "representative", "agent", "person", "speak with someone", "escalate"]):
        return "human_handoff"
    if any(k in query for k in ["test drive", "drive", "slot", "book", "appointment", "schedule"]):
        return "test_drive_booking"
    if any(k in query for k in ["car", "vehicle", "price", "inventory", "stock", "model", "buy", "cost"]):
        return "inventory_inquiry"
    if any(k in query for k in ["hour", "open", "close", "location", "address", "phone", "direction"]):
        return "dealership_info"
    return "general"


def _build_suggested_actions(intent: str, has_vehicles: bool, has_slots: bool) -> list[str]:
    actions = []
    if intent == "inventory_inquiry" and has_slots:
        actions.append("Book a test drive for this vehicle")
        actions.append("View detailed vehicle specifications")
    elif intent == "test_drive_booking":
        actions.append("Select a slot and confirm booking")
        actions.append("Check vehicle availability")
    elif intent == "human_handoff":
        actions.append("Request callback from a representative")
    else:
        if has_vehicles:
            actions.append("Browse available vehicles")
        if has_slots:
            actions.append("Schedule a test drive")
        actions.append("Ask about dealership hours and location")
    return actions
