import math
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.channel import Conversation, ConversationMessage
from app.models.user import User
from app.services import audit_service, conversation_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}/conversations",
    tags=["Conversation Inbox"],
)


class ConversationMessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_type: str
    sender_id: int | None = None
    content: str
    channel_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummaryOut(BaseModel):
    id: int
    dealership_id: int
    channel: str
    channel_user_id: str
    email_subject: str | None = None
    customer_id: int | None = None
    status: str
    assigned_to_user_id: int | None = None
    assigned_to_name: str | None = None
    handoff_reason: str | None = None
    last_message_preview: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationSummaryOut):
    messages: list[ConversationMessageOut] = Field(default_factory=list)


class ConversationStatusUpdateRequest(BaseModel):
    status: Literal["active", "handed_off", "closed"]
    assigned_to_user_id: int | None = Field(default=None, ge=1)
    handoff_reason: str | None = Field(default=None, max_length=500)


class ConversationStaffReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ConversationMessageRedactRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def _to_summary(conv: Conversation) -> ConversationSummaryOut:
    meta = conv.channel_metadata or {}
    msgs = conv.messages or []
    last_msg = msgs[-1].content[:140] if msgs else None
    return ConversationSummaryOut(
        id=conv.id,
        dealership_id=conv.dealership_id,
        channel=conv.channel,
        channel_user_id=conv.channel_user_id,
        email_subject=meta.get("email_subject"),
        customer_id=conv.customer_id,
        status=conv.status,
        assigned_to_user_id=meta.get("assigned_to_user_id"),
        assigned_to_name=meta.get("assigned_to_name"),
        handoff_reason=meta.get("handoff_reason"),
        last_message_preview=last_msg,
        message_count=len(msgs),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("", response_model=list[ConversationSummaryOut])
def list_conversations(
    dealership_id: int,
    response: Response,
    channel: Literal["website", "whatsapp", "voice", "email"] | None = Query(default=None),
    conv_status: Literal["active", "handed_off", "closed"] | None = Query(
        default=None, alias="status"
    ),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[ConversationSummaryOut]:
    items = conversation_service.list_conversations(
        db,
        dealership_id,
        channel=channel,
        status=conv_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    total = conversation_service.count_conversations(
        db,
        dealership_id,
        channel=channel,
        status=conv_status,
        search=search,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(
        math.ceil(total / page_size) if page_size > 0 else 1
    )
    return [_to_summary(conv) for conv in items]


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation_detail(
    dealership_id: int,
    conversation_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ConversationDetailOut:
    conv = conversation_service.get_conversation_for_dealership(
        db, dealership_id, conversation_id
    )
    summary = _to_summary(conv)
    return ConversationDetailOut(
        **summary.model_dump(),
        messages=[ConversationMessageOut.model_validate(m) for m in (conv.messages or [])],
    )


@router.patch("/{conversation_id}/status", response_model=ConversationDetailOut)
def update_conversation_status(
    dealership_id: int,
    conversation_id: int,
    payload: ConversationStatusUpdateRequest,
    request: Request,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ConversationDetailOut:
    conv = conversation_service.update_conversation_status(
        db,
        dealership_id,
        conversation_id,
        status=payload.status,
        staff_user=current_user,
        assigned_to_user_id=payload.assigned_to_user_id,
        assignment_provided="assigned_to_user_id" in payload.model_fields_set,
        handoff_reason=payload.handoff_reason,
    )
    audit_service.log_event(
        db,
        action="conversation.status_changed",
        resource_type="conversation",
        resource_id=str(conv.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={
            "status": conv.status,
            "assigned_to_user_id": payload.assigned_to_user_id,
            "handoff_reason": payload.handoff_reason,
        },
    )
    summary = _to_summary(conv)
    return ConversationDetailOut(
        **summary.model_dump(),
        messages=[ConversationMessageOut.model_validate(m) for m in (conv.messages or [])],
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def post_staff_reply(
    dealership_id: int,
    conversation_id: int,
    payload: ConversationStaffReplyRequest,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ConversationMessageOut:
    msg: ConversationMessage = conversation_service.add_staff_reply(
        db,
        dealership_id,
        conversation_id,
        current_user,
        payload.content,
    )
    return ConversationMessageOut.model_validate(msg)


@router.post(
    "/{conversation_id}/messages/{message_id}/redact",
    response_model=ConversationMessageOut,
)
def redact_conversation_message(
    dealership_id: int,
    conversation_id: int,
    message_id: int,
    request: Request,
    payload: ConversationMessageRedactRequest | None = None,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> ConversationMessageOut:
    reason = payload.reason if payload else None
    msg = conversation_service.redact_message(
        db,
        dealership_id,
        conversation_id,
        message_id,
        current_user,
        reason=reason,
    )
    audit_service.log_event(
        db,
        action="conversation_message.redacted",
        resource_type="conversation_message",
        resource_id=str(msg.id),
        dealership_id=dealership_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        details={"conversation_id": conversation_id, "reason": reason},
    )
    return ConversationMessageOut.model_validate(msg)
