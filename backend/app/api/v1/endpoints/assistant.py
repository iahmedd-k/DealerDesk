from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.models.user import User
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services import assistant_service, audit_service

router = APIRouter(
    prefix="/dealerships/{dealership_id}/assistant",
    tags=["Dealership AI Assistant"],
)


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Chat with Dealership AI Assistant",
    description=(
        "Customer-facing, dealership-scoped AI assistant grounded in real-time "
        "inventory catalog, test-drive schedule availability, and dealership knowledge base."
    ),
)
def chat_with_dealership_assistant(
    dealership_id: int,
    payload: AssistantChatRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> AssistantChatResponse:
    response = assistant_service.chat_with_assistant(
        db,
        dealership_id,
        payload,
        current_user=current_user,
    )

    # Record interaction in audit logs
    client_ip = request.client.host if request.client else None
    audit_service.log_event(
        db,
        action="assistant.chat",
        resource_type="dealership",
        resource_id=str(dealership_id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=client_ip,
        details={
            "intent": response.intent,
            "channel": payload.channel,
            "matched_vehicles": len(response.matched_vehicles),
            "available_slots": len(response.available_slots),
            "sources_count": len(response.sources),
        },
    )

    return response
