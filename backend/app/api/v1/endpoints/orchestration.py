from typing import Any
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.models.user import User
from app.orchestration import orchestrator
from app.schemas.channel import ChannelEvent

router = APIRouter(prefix="/dealerships/{dealership_id}/orchestrate", tags=["Central Orchestration"])


@router.post(
    "",
    summary="Central Agent Orchestration Dispatch",
    description="Dispatches normalized channel events to the appropriate agent (Sales Agent or CRM Agent).",
)
@limiter.limit("60/minute")
def orchestrate_event(
    request: Request,
    dealership_id: int,
    event: ChannelEvent,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict[str, Any]:
    # Ensure event dealership_id matches path
    if event.dealership_id != dealership_id:
        event.dealership_id = dealership_id

    result = orchestrator.dispatch_event(
        db,
        event=event,
        current_user=current_user,
    )

    return {
        "target_agent": result.target_agent,
        "channel": result.channel,
        "dealership_id": result.dealership_id,
        "conversation_id": result.conversation_id,
        "customer_id": result.customer_id,
        "response_text": result.response_text,
        "outbound": result.outbound_payload,
        "metadata": result.metadata,
    }
