import logging
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.adapters import get_channel_adapter
from app.adapters.voice_adapter import VoiceAdapter
from app.adapters.whatsapp_adapter import WhatsAppAdapter
from app.core.circuit_breaker import voice_circuit_breaker, whatsapp_circuit_breaker
from app.core.limiter import limiter
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.models.user import User
from app.orchestration import orchestrator
from app.schemas.channel import ChannelType

logger = logging.getLogger("dealerdesk.channels")

router = APIRouter(prefix="/dealerships/{dealership_id}/channels", tags=["Channel Adapters"])


# =====================================================================
# 1. WEBSITE CHATBOT CHANNEL
# =====================================================================

@router.post(
    "/website/message",
    summary="Website Chatbot Inbound Message",
    description="Processes messages arriving from the website customer chat widget.",
)
@limiter.limit("30/minute")
def website_channel_message(
    request: Request,
    dealership_id: int,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict[str, Any]:
    adapter = get_channel_adapter(ChannelType.WEBSITE)
    event = adapter.parse_inbound(dealership_id, payload, dict(request.headers))
    result = orchestrator.dispatch_event(db, event, current_user=current_user)
    return result.outbound_payload


# =====================================================================
# 2. WHATSAPP BUSINESS CHANNEL
# =====================================================================

@router.get(
    "/whatsapp/webhook",
    summary="WhatsApp Webhook Verification",
    description="Responds to Meta WhatsApp webhook challenge verification.",
)
def verify_whatsapp_webhook(
    dealership_id: int,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
) -> Response:
    expected_token = "dealerdesk_whatsapp_verify_token"
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("WhatsApp webhook verified for dealership %d", dealership_id)
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=status.HTTP_403_FORBIDDEN)


@router.post(
    "/whatsapp/webhook",
    summary="WhatsApp Inbound Webhook",
    description="Processes incoming customer messages and quick-replies from WhatsApp.",
)
def handle_whatsapp_webhook(
    dealership_id: int,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    adapter: WhatsAppAdapter = get_channel_adapter(ChannelType.WHATSAPP)  # type: ignore

    event = adapter.parse_inbound(dealership_id, payload, dict(request.headers))

    # De-duplicate webhook retries
    if event.metadata.get("is_duplicate"):
        return {"status": "ok", "message": "Duplicate event ignored"}

    if not event.message.strip():
        return {"status": "ok", "message": "No actionable message content"}

    try:
        result = whatsapp_circuit_breaker.call(
            orchestrator.dispatch_event,
            db,
            event=event,
        )
        return {"status": "ok", "outbound": result.outbound_payload}
    except Exception as exc:
        logger.error("WhatsApp channel processing failed: %s", exc)
        return {"status": "error", "message": "Channel temporarily unavailable"}


# =====================================================================
# 3. VOICE TELEPHONY CHANNEL
# =====================================================================

@router.post(
    "/voice/webhook",
    summary="Voice Telephony Inbound Webhook",
    description="Handles incoming telephone calls and speech recognition input, returning TwiML spoken audio.",
)
async def handle_voice_webhook(
    dealership_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    adapter: VoiceAdapter = get_channel_adapter(ChannelType.VOICE)  # type: ignore

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form_data = await request.form()
        payload = dict(form_data)

    event = adapter.parse_inbound(dealership_id, payload, dict(request.headers))

    try:
        result = voice_circuit_breaker.call(
            orchestrator.dispatch_event,
            db,
            event=event,
        )
        return Response(content=result.outbound_payload["twiml"], media_type="application/xml")
    except Exception as exc:
        logger.error("Voice channel processing failed: %s", exc)
        fallback_twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            "    <Say voice=\"Polly.Joanna-Neural\">Thank you for calling. Our dealership representative will call you shortly.</Say>\n"
            "    <Hangup/>\n"
            "</Response>"
        )
        return Response(content=fallback_twiml, media_type="application/xml")
