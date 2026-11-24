from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.models.user import User
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services import assistant_service, audit_service

router = APIRouter(
    prefix="/dealerships/{dealership_id}/assistant",
    tags=["Dealership AI Assistant"],
)


@limiter.limit(get_settings().assistant_rate_limit)
@router.post(
    "/chat/stream",
    summary="Stream Chat with Dealership AI Assistant",
    description=(
        "Streams token-by-token response over Server-Sent Events (SSE) "
        "with active prompt injection and PII safety guardrails."
    ),
)
async def stream_chat_with_dealership_assistant(
    dealership_id: int,
    payload: AssistantChatRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    assistant_service.validate_assistant_scope(db, dealership_id, current_user)
    client_ip = request.client.host if request.client else None
    audit_service.log_event(
        db,
        action="assistant.chat_stream",
        resource_type="dealership",
        resource_id=str(dealership_id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=client_ip,
        details={"channel": payload.channel},
    )

    generator = assistant_service.stream_chat_with_assistant(
        db,
        dealership_id,
        payload,
        current_user=current_user,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@limiter.limit(get_settings().assistant_rate_limit)
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
