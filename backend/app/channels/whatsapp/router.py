import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.channels.whatsapp.service import get_whatsapp_service
from app.core.config import get_settings
from app.db.session import get_db
from app.models.channel import (
    Conversation,
    ConversationMessage,
    TwilioDeliveryStatus,
    TwilioWebhookReceipt,
)
from app.models.workspace import Dealership
from app.orchestration import orchestrator
from app.schemas.channel import ChannelEvent, ChannelType

logger = logging.getLogger("dealerdesk.channels.whatsapp")

router = APIRouter()
GENERIC_REPLY = "Thanks for contacting the dealership. A team member will follow up shortly."
_DELIVERY_STATUS_ORDER = {
    "accepted": 0,
    "scheduled": 0,
    "queued": 0,
    "sending": 1,
    "sent": 2,
    "delivered": 3,
    "read": 4,
    "failed": 3,
    "undelivered": 3,
    "canceled": 3,
}
_FAILED_DELIVERY_STATUSES = {"failed", "undelivered", "canceled"}


def _normalized_number(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value)


def _signature_url(request: Request) -> str:
    settings = get_settings()
    if not settings.twilio_webhook_base_url:
        return str(request.url)
    parsed_request = urlsplit(str(request.url))
    parsed_base = urlsplit(settings.twilio_webhook_base_url)
    if parsed_base.scheme not in {"https", "http"} or not parsed_base.netloc:
        raise HTTPException(status_code=503, detail="Twilio webhook URL is not configured correctly.")
    return urlunsplit(
        (
            parsed_base.scheme,
            parsed_base.netloc,
            parsed_request.path,
            parsed_request.query,
            "",
        )
    )


async def _validated_twilio_form(request: Request):
    settings = get_settings()
    if settings.twilio_auth_token is None:
        raise HTTPException(status_code=503, detail="Twilio webhook validation is not configured.")
    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    validator = RequestValidator(settings.twilio_auth_token.get_secret_value())
    if not signature or not validator.validate(_signature_url(request), form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")
    return form


def _dealership_for_number(db: Session, number: str) -> Dealership:
    normalized = _normalized_number(number)
    matches = [
        dealership
        for dealership in db.scalars(
            select(Dealership).where(
                Dealership.is_active.is_(True),
                Dealership.whatsapp_number.is_not(None),
            )
        )
        if _normalized_number(dealership.whatsapp_number) == normalized
    ]
    if len(matches) != 1:
        if not matches:
            raise HTTPException(status_code=404, detail="No dealership is configured for this WhatsApp number.")
        raise HTTPException(status_code=409, detail="WhatsApp number is assigned to multiple dealerships.")
    return matches[0]


def _twiml(text: str) -> Response:
    return Response(
        content=get_whatsapp_service().create_twiml_reply(text),
        media_type="application/xml",
    )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_delivery_status_advance(current: str | None, incoming: str) -> bool:
    if incoming not in _DELIVERY_STATUS_ORDER:
        return False
    if current is None:
        return True
    if current in _FAILED_DELIVERY_STATUSES:
        return False
    if current in {"delivered", "read"} and incoming in _FAILED_DELIVERY_STATUSES:
        return False
    return _DELIVERY_STATUS_ORDER[incoming] >= _DELIVERY_STATUS_ORDER.get(current, -1)


@router.get(
    "/webhook",
    summary="WhatsApp Webhook Health Check",
    description="Confirms that the Twilio WhatsApp webhook adapter is operational.",
)
async def whatsapp_webhook_status() -> dict[str, Any]:
    return {
        "status": "online",
        "channel": "whatsapp",
        "provider": "twilio",
        "endpoint": "POST /webhook",
    }


@router.post(
    "/webhook",
    summary="Twilio WhatsApp Inbound Webhook",
    description="Receives incoming WhatsApp messages from Twilio, dispatches to Customer Sales Agent, and returns a TwiML response.",
)
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    form = await _validated_twilio_form(request)
    sender = str(form.get("From") or "").strip()
    destination = str(form.get("To") or "").strip()
    body = str(form.get("Body") or "").strip()
    message_sid = str(form.get("MessageSid") or "").strip()
    profile_name = str(form.get("ProfileName") or "").strip() or None
    if not sender or not destination or not body or not message_sid:
        raise HTTPException(
            status_code=400,
            detail="Twilio WhatsApp webhook is missing a required field.",
        )

    dealership = _dealership_for_number(db, destination)
    clean_phone = sender.removeprefix("whatsapp:").strip()
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Twilio sender number is invalid.")

    receipt = db.scalar(
        select(TwilioWebhookReceipt)
        .where(TwilioWebhookReceipt.message_sid == message_sid)
        .with_for_update()
    )
    if receipt is not None and receipt.dealership_id != dealership.id:
        raise HTTPException(status_code=409, detail="Twilio message is already associated with another dealership.")
    if receipt is not None and receipt.status == "completed":
        return _twiml(receipt.response_text or GENERIC_REPLY)
    if (
        receipt is not None
        and receipt.status == "processing"
        and receipt.updated_at is not None
        and receipt.updated_at > _now_utc() - timedelta(minutes=5)
    ):
        return _twiml(receipt.response_text or GENERIC_REPLY)
    if receipt is None:
        receipt = TwilioWebhookReceipt(
            message_sid=message_sid,
            dealership_id=dealership.id,
            status="processing",
            attempts=1,
        )
        db.add(receipt)
    else:
        receipt.status = "processing"
        receipt.attempts += 1
        receipt.updated_at = _now_utc()
    try:
        db.commit()
        db.refresh(receipt)
    except IntegrityError:
        db.rollback()
        existing_receipt = db.scalar(
            select(TwilioWebhookReceipt).where(
                TwilioWebhookReceipt.message_sid == message_sid
            )
        )
        return _twiml(
            existing_receipt.response_text
            if existing_receipt and existing_receipt.response_text
            else GENERIC_REPLY
        )

    try:
        event = ChannelEvent(
            dealership_id=dealership.id,
            channel=ChannelType.WHATSAPP,
            channel_user_id=clean_phone,
            message=body,
            metadata={
                "profile_name": profile_name,
                "message_sid": message_sid,
            },
        )
        result = orchestrator.dispatch_event(db, event)
        reply_text = result.response_text if result and result.response_text else GENERIC_REPLY
        receipt.status = "completed"
        receipt.response_text = reply_text
        receipt.updated_at = _now_utc()
        db.commit()
        logger.info("Processed Twilio WhatsApp inbound message sid=%s dealership_id=%s", message_sid, dealership.id)
        return _twiml(reply_text)
    except Exception as exc:
        db.rollback()
        receipt = db.scalar(
            select(TwilioWebhookReceipt).where(
                TwilioWebhookReceipt.message_sid == message_sid
            )
        )
        if receipt is not None:
            receipt.status = "failed"
            receipt.updated_at = _now_utc()
            db.commit()
        logger.error(
            "Twilio WhatsApp processing failed sid=%s error_type=%s",
            message_sid,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="The dealership could not process this WhatsApp message.",
        ) from exc


@router.post(
    "/status",
    summary="Twilio WhatsApp Message Status Callback",
    description="Receives delivery status updates (queued, sent, delivered, read, failed).",
)
async def whatsapp_status_callback(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    form = await _validated_twilio_form(request)
    message_sid = str(form.get("MessageSid") or "").strip()
    message_status = str(form.get("MessageStatus") or "").strip().lower()
    from_number = str(form.get("From") or "").strip()
    recipient = str(form.get("To") or "").strip()
    if not message_sid or not message_status or not from_number or not recipient:
        raise HTTPException(status_code=400, detail="Twilio status callback is missing a required field.")
    if message_status not in _DELIVERY_STATUS_ORDER:
        raise HTTPException(status_code=400, detail="Twilio status callback has an unsupported status.")

    message = db.scalar(
        select(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(ConversationMessage.external_message_id == message_sid)
    )
    dealership_id = (
        message.conversation.dealership_id
        if message is not None
        else _dealership_for_number(db, from_number).id
    )
    delivery = db.scalar(
        select(TwilioDeliveryStatus).where(
            TwilioDeliveryStatus.message_sid == message_sid
        )
    )
    now = _now_utc()
    message_metadata = dict(message.channel_metadata or {}) if message is not None else {}
    current_status = (
        delivery.status
        if delivery is not None
        else message_metadata.get("provider_status")
    )
    advances_status = _is_delivery_status_advance(current_status, message_status)
    persisted_status = message_status if advances_status else current_status
    if delivery is None:
        delivery = TwilioDeliveryStatus(
            message_sid=message_sid,
            dealership_id=dealership_id,
            recipient=recipient,
            status=persisted_status or message_status,
            updated_at=now,
        )
        db.add(delivery)
    elif advances_status:
        delivery.status = message_status
        delivery.updated_at = now
    if message is not None and advances_status:
        message_metadata["provider_status"] = message_status
        message_metadata["provider_status_updated_at"] = now.isoformat()
        message.channel_metadata = message_metadata
    db.commit()
    logger.info("Twilio WhatsApp delivery status updated sid=%s status=%s", message_sid, message_status)
    return {"status": "ok"}
