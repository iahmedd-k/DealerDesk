from datetime import datetime, timezone
import re
from typing import Any
from sqlalchemy.orm import Session

from app.models.channel import Conversation, ConversationMessage
from app.models.user import User


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
) -> ConversationMessage:
    """
    Appends a new message turn to the persistent conversation log.
    """
    now = datetime.now(timezone.utc)
    message = ConversationMessage(
        conversation_id=conversation_id,
        sender_type=sender_type,
        sender_id=sender_id,
        content=content,
        channel_metadata=channel_metadata or {},
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

