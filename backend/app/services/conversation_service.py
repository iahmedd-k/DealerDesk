from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.channel import Conversation, ConversationMessage, TwilioDeliveryStatus
from app.models.user import User
from app.models.workspace import Dealership

_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")


def scrub_sensitive_pii(text: str, *, include_contact_pii: bool = False) -> tuple[str, bool]:
    """
    Redacts high-risk PII (payment cards, SSNs) on ingestion, and optionally
    contact PII (emails, phone numbers) during aged transcript retention passes.
    """
    scrubbed = _CARD_PATTERN.sub("[REDACTED_CARD]", text)
    scrubbed = _SSN_PATTERN.sub("[REDACTED_SSN]", scrubbed)
    if include_contact_pii:
        scrubbed = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", scrubbed)
        scrubbed = _PHONE_PATTERN.sub("[REDACTED_PHONE]", scrubbed)
    return scrubbed, scrubbed != text


def get_or_create_conversation(
    db: Session,
    dealership_id: int,
    channel: str,
    channel_user_id: str,
    customer_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> Conversation:
    """
    Finds the active conversation for a user on a given channel, or initiates a new one.
    Automatically links verified customer identity across channels.
    """
    resolved_customer_id = customer_id
    if resolved_customer_id is None:
        clean_uid = channel_user_id.strip().lower()
        if "@" in clean_uid:
            user = db.query(User).filter(User.email == clean_uid).first()
            if user:
                resolved_customer_id = user.id
        else:
            phone_digits = re.sub(r"\D", "", clean_uid)
            if len(phone_digits) >= 7:
                candidate_email = f"phone_{phone_digits}@customer.dealerdesk.local"
                user = db.query(User).filter(User.email == candidate_email).first()
                if user:
                    resolved_customer_id = user.id

        if resolved_customer_id is None:
            prev_conv = (
                db.query(Conversation)
                .filter(
                    Conversation.dealership_id == dealership_id,
                    Conversation.channel_user_id == channel_user_id,
                    Conversation.customer_id.isnot(None),
                )
                .first()
            )
            if prev_conv:
                resolved_customer_id = prev_conv.customer_id

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.dealership_id == dealership_id,
            Conversation.channel == channel,
            Conversation.channel_user_id == channel_user_id,
            Conversation.status == "active",
        )
        .order_by(Conversation.updated_at.desc())
        .first()
    )

    if conversation is None:
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            dealership_id=dealership_id,
            channel=channel,
            channel_user_id=channel_user_id,
            customer_id=resolved_customer_id,
            status="active",
            channel_metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    elif resolved_customer_id and not conversation.customer_id:
        conversation.customer_id = resolved_customer_id
        db.commit()

    return conversation



def append_message(
    db: Session,
    conversation_id: int,
    sender_type: str,
    content: str,
    sender_id: int | None = None,
    channel_metadata: dict[str, Any] | None = None,
    external_message_id: str | None = None,
) -> ConversationMessage:
    """
    Appends a new message turn to the persistent conversation log,
    automatically scrubbing high-risk payment/SSN PII on ingestion.
    """
    now = datetime.now(timezone.utc)
    clean_content, was_scrubbed = scrub_sensitive_pii(content, include_contact_pii=False)
    meta = dict(channel_metadata or {})
    if was_scrubbed:
        meta["pii_scrubbed_on_ingest"] = True
    message = ConversationMessage(
        conversation_id=conversation_id,
        sender_type=sender_type,
        sender_id=sender_id,
        content=clean_content,
        external_message_id=external_message_id,
        channel_metadata=meta,
        created_at=now,
    )
    db.add(message)

    # Touch conversation updated_at timestamp
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.updated_at = now

    db.commit()
    db.refresh(message)
    return message


def get_conversation_history(
    db: Session,
    conversation_id: int,
    limit: int = 10,
) -> list[ConversationMessage]:
    """
    Retrieves the most recent messages in chronological order for prompt synthesis.
    """
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def link_customer(db: Session, conversation_id: int, customer_id: int) -> Conversation | None:
    """
    Links a verified customer identity to an active conversation session.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.customer_id = customer_id
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(conversation)
    return conversation


def list_conversations(
    db: Session,
    dealership_id: int,
    *,
    channel: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> list[Conversation]:
    query = db.query(Conversation).filter(Conversation.dealership_id == dealership_id)
    if channel:
        query = query.filter(Conversation.channel == channel)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(Conversation.channel_user_id.ilike(pattern))
    offset = max(0, (page - 1) * page_size)
    return (
        query.order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )


def count_conversations(
    db: Session,
    dealership_id: int,
    *,
    channel: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> int:
    query = db.query(func.count(Conversation.id)).filter(
        Conversation.dealership_id == dealership_id
    )
    if channel:
        query = query.filter(Conversation.channel == channel)
    if status:
        query = query.filter(Conversation.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(Conversation.channel_user_id.ilike(pattern))
    return query.scalar() or 0


def get_conversation_for_dealership(
    db: Session,
    dealership_id: int,
    conversation_id: int,
) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.dealership_id == dealership_id,
        )
        .first()
    )
    if conv is None:
        raise NotFoundError("Conversation not found")
    return conv


def update_conversation_status(
    db: Session,
    dealership_id: int,
    conversation_id: int,
    *,
    status: str,
    staff_user: User,
    assigned_to_user_id: int | None = None,
    assignment_provided: bool = False,
    handoff_reason: str | None = None,
) -> Conversation:
    conv = get_conversation_for_dealership(db, dealership_id, conversation_id)
    now = datetime.now(timezone.utc)
    prev_status = conv.status
    conv.status = status
    meta = dict(conv.channel_metadata or {})
    if assignment_provided:
        if assigned_to_user_id is None:
            meta.pop("assigned_to_user_id", None)
            meta.pop("assigned_to_name", None)
        else:
            assignee = (
                db.query(User)
                .filter(
                    User.id == assigned_to_user_id,
                    User.dealership_id == dealership_id,
                    User.role.in_({"dealership_admin", "manager", "sales_rep"}),
                    User.is_active.is_(True),
                )
                .first()
            )
            if assignee is None:
                raise NotFoundError("Active dealership staff member not found")
            meta["assigned_to_user_id"] = assignee.id
            meta["assigned_to_name"] = assignee.name
    if handoff_reason is not None:
        meta["handoff_reason"] = handoff_reason.strip()
    meta["updated_by_user_id"] = staff_user.id
    conv.channel_metadata = meta
    conv.updated_at = now
    db.commit()
    db.refresh(conv)

    if prev_status != status:
        append_message(
            db,
            conv.id,
            sender_type="system",
            content=(
                f"Conversation status changed from '{prev_status}' to '{status}' by {staff_user.name}"
                + (f" ({handoff_reason.strip()})" if handoff_reason and handoff_reason.strip() else "")
            ),
            sender_id=staff_user.id,
        )
        db.refresh(conv)
    return conv


def add_staff_reply(
    db: Session,
    dealership_id: int,
    conversation_id: int,
    staff_user: User,
    content: str,
) -> ConversationMessage:
    conv = get_conversation_for_dealership(db, dealership_id, conversation_id)
    metadata: dict[str, Any] = {
        "staff_name": staff_user.name,
        "staff_email": staff_user.email,
    }
    external_message_id = None
    if conv.channel == "email":
        from app.services import gmail_service

        provider_message = gmail_service.send_reply(
            db,
            conv,
            staff_user,
            content.strip(),
        )
        external_message_id = provider_message["provider_message_id"]
        metadata.update(
            {
                "provider": "gmail",
                "rfc822_message_id": provider_message["rfc822_message_id"],
                "references": provider_message.get("references", ""),
                "provider_status": "sent",
            }
        )
    elif conv.channel == "whatsapp":
        from app.channels.whatsapp.service import get_whatsapp_service
        from app.core.config import get_settings

        dealership = db.get(Dealership, dealership_id)
        if dealership is None or not dealership.is_active:
            raise NotFoundError("Dealership not found")
        if not dealership.whatsapp_number:
            raise ConflictError("Configure a WhatsApp number in Settings before replying.")
        provider_message = get_whatsapp_service().send_message(
            to=conv.channel_user_id,
            body=content.strip(),
            from_override=f"whatsapp:{dealership.whatsapp_number}",
            status_callback=get_settings().twilio_status_callback_url,
        )
        external_message_id = provider_message["sid"]
        latest_status = db.scalar(
            select(TwilioDeliveryStatus).where(
                TwilioDeliveryStatus.message_sid == provider_message["sid"]
            )
        )
        metadata.update(
            {
                "provider": "twilio",
                "provider_status": (
                    latest_status.status
                    if latest_status is not None
                    else provider_message.get("status", "queued")
                ),
            }
        )
    else:
        raise UnprocessableEntityError(
            "Replies are not supported for this channel yet; use the original channel to contact the customer."
        )
    return append_message(
        db,
        conv.id,
        sender_type="staff",
        content=content.strip(),
        sender_id=staff_user.id,
        channel_metadata=metadata,
        external_message_id=external_message_id,
    )


def redact_message(
    db: Session,
    dealership_id: int,
    conversation_id: int,
    message_id: int,
    staff_user: User,
    reason: str | None = None,
) -> ConversationMessage:
    conv = get_conversation_for_dealership(db, dealership_id, conversation_id)
    msg = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.id == message_id,
            ConversationMessage.conversation_id == conv.id,
        )
        .first()
    )
    if msg is None:
        raise NotFoundError("Message not found")

    now = datetime.now(timezone.utc)
    meta = dict(msg.channel_metadata or {})
    meta["redacted"] = True
    meta["redacted_at"] = now.isoformat()
    meta["redacted_by_user_id"] = staff_user.id
    if reason and reason.strip():
        meta["redaction_reason"] = reason.strip()

    msg.content = "[REDACTED BY STAFF]"
    msg.channel_metadata = meta
    db.commit()
    db.refresh(msg)
    return msg

