import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

from app.channels.whatsapp.service import get_whatsapp_service
from app.db.session import get_db
from app.models.workspace import Dealership
from app.orchestration import orchestrator
from app.schemas.channel import ChannelEvent, ChannelType

logger = logging.getLogger("dealerdesk.channels.whatsapp")

router = APIRouter()


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
    sender: str = Form(..., alias="From"),
    body: str = Form(..., alias="Body"),
    profile_name: str | None = Form(None, alias="ProfileName"),
    message_sid: str | None = Form(None, alias="MessageSid"),
    wa_id: str | None = Form(None, alias="WaId"),
    db: Session = Depends(get_db),
) -> Response:
    """
    Receives incoming WhatsApp message webhook from Twilio Sandbox / Business API,
    passes it through the Customer Sales Agent orchestrator, and responds with TwiML.
    """
    display_sender = f"{profile_name} ({sender})" if profile_name else sender
    print(f"Message from {display_sender}: {body}")
    logger.info("Twilio WhatsApp inbound from %s (SID: %s): %s", display_sender, message_sid, body)

    clean_phone = sender.replace("whatsapp:", "").strip()

    # Attempt to process through Customer Sales Agent via Central Orchestrator
    reply_text = "Hello! Welcome to our dealership."
    try:
        dealership = db.query(Dealership).filter(Dealership.is_active.is_(True)).first()
        if dealership and body.strip():
            event = ChannelEvent(
                dealership_id=dealership.id,
                channel=ChannelType.WHATSAPP,
                channel_user_id=clean_phone,
                message=body,
                metadata={
                    "profile_name": profile_name,
                    "message_sid": message_sid,
                    "wa_id": wa_id,
                    "sender_raw": sender,
                },
            )
            result = orchestrator.dispatch_event(db, event)
            if result and result.response_text:
                reply_text = result.response_text
    except Exception as exc:
        logger.warning("Sales agent processing fallback: %s", exc)

    # Respond to Twilio synchronously via TwiML XML
    twiml = MessagingResponse()
    twiml.message(reply_text)

    return Response(
        content=str(twiml),
        media_type="application/xml",
    )


@router.post(
    "/status",
    summary="Twilio WhatsApp Message Status Callback",
    description="Receives delivery status updates (queued, sent, delivered, read, failed).",
)
async def whatsapp_status_callback(
    message_sid: str | None = Form(None, alias="MessageSid"),
    message_status: str | None = Form(None, alias="MessageStatus"),
    to: str | None = Form(None, alias="To"),
) -> dict[str, str]:
    logger.info("Twilio status update for %s: %s (to %s)", message_sid, message_status, to)
    return {"status": "ok"}
