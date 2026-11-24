import hashlib
import hmac
import logging
import time
from typing import Any
from app.adapters.base import BaseChannelAdapter
from app.schemas.channel import ChannelEvent, ChannelType
from app.schemas.sales_agent import SalesAgentChatResponse

logger = logging.getLogger("dealerdesk.whatsapp")

# In-memory LRU/TTL cache for WhatsApp webhook de-duplication
_PROCESSED_MESSAGE_IDS: dict[str, float] = {}
DEDUPLICATION_WINDOW_SECONDS = 300.0  # 5 minutes


class WhatsAppAdapter(BaseChannelAdapter):
    """
    WhatsApp Cloud API / Twilio WhatsApp Adapter.
    Handles inbound webhook normalization (text, quick replies, list selections),
    HMAC-SHA256 signature verification, message de-duplication, and
    outbound interactive button/list message synthesis.
    """

    channel_type = ChannelType.WHATSAPP

    def verify_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Validates X-Hub-Signature-256 header against WhatsApp app secret.
        """
        if not signature or not secret:
            return False

        expected_prefix = "sha256="
        sig_value = signature[len(expected_prefix):] if signature.startswith(expected_prefix) else signature
        computed = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, sig_value)

    def is_duplicate_message(self, message_id: str) -> bool:
        """
        Prevents duplicate webhook events from triggering re-executions.
        """
        now = time.time()
        # Clean expired entries
        expired_keys = [k for k, ts in _PROCESSED_MESSAGE_IDS.items() if now - ts > DEDUPLICATION_WINDOW_SECONDS]
        for k in expired_keys:
            del _PROCESSED_MESSAGE_IDS[k]

        if message_id in _PROCESSED_MESSAGE_IDS:
            logger.info("Ignoring duplicate WhatsApp message ID: %s", message_id)
            return True

        _PROCESSED_MESSAGE_IDS[message_id] = now
        return False

    def parse_inbound(
        self,
        dealership_id: int,
        payload: dict[str, Any] | str,
        headers: dict[str, str] | None = None,
    ) -> ChannelEvent:
        """
        Normalizes Meta Cloud API or Twilio WhatsApp payload into ChannelEvent.
        """
        if isinstance(payload, str):
            return ChannelEvent(
                dealership_id=dealership_id,
                channel=self.channel_type,
                channel_user_id="unknown_whatsapp_user",
                message=payload,
            )

        # 1. Meta WhatsApp Cloud API format:
        # payload -> entry[] -> changes[] -> value -> messages[]
        if "entry" in payload:
            try:
                entry = payload["entry"][0]
                change = entry["changes"][0]
                value = change["value"]
                message_obj = value["messages"][0]
                sender_phone = message_obj["from"]
                message_id = message_obj.get("id", "")

                # Check de-duplication
                is_duplicate = self.is_duplicate_message(message_id) if message_id else False

                msg_type = message_obj.get("type", "text")
                text_content = ""
                if msg_type == "text":
                    text_content = message_obj["text"]["body"]
                elif msg_type == "interactive":
                    interactive = message_obj["interactive"]
                    if interactive.get("type") == "button_reply":
                        text_content = interactive["button_reply"]["title"]
                    elif interactive.get("type") == "list_reply":
                        text_content = interactive["list_reply"]["title"]
                elif msg_type == "button":
                    text_content = message_obj["button"]["text"]
                else:
                    text_content = f"[{msg_type} message received]"

                return ChannelEvent(
                    dealership_id=dealership_id,
                    channel=self.channel_type,
                    channel_user_id=sender_phone,
                    message=text_content,
                    metadata={
                        "message_id": message_id,
                        "is_duplicate": is_duplicate,
                        "raw_type": msg_type,
                        "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
                    },
                )
            except (KeyError, IndexError, TypeError) as exc:
                logger.warning("Could not parse Meta WhatsApp webhook structure: %s", exc)

        # 2. Twilio WhatsApp format: From=whatsapp:+123..., Body=...
        if "From" in payload and "Body" in payload:
            sender = payload["From"].replace("whatsapp:", "")
            msg_id = payload.get("MessageSid", "")
            return ChannelEvent(
                dealership_id=dealership_id,
                channel=self.channel_type,
                channel_user_id=sender,
                message=payload["Body"],
                metadata={"message_id": msg_id, "is_duplicate": self.is_duplicate_message(msg_id) if msg_id else False},
            )

        # 3. Direct/Normalized fallback format
        phone = str(payload.get("phone") or payload.get("channel_user_id") or "unknown")
        msg = str(payload.get("message") or payload.get("text") or "")
        return ChannelEvent(
            dealership_id=dealership_id,
            channel=self.channel_type,
            channel_user_id=phone,
            message=msg,
            metadata=payload,
        )

    def format_outbound(
        self,
        response: SalesAgentChatResponse,
        recipient: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Formats response into WhatsApp interactive messages or plain formatted text.
        """
        phone_number = recipient.replace("whatsapp:", "").replace("+", "").strip()

        # Build interactive quick-reply buttons if actions are available
        buttons = []
        for i, action in enumerate(response.suggested_actions[:3]):
            clean_title = action[:20]  # WhatsApp max button title length is 20 chars
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"btn_{i+1}",
                    "title": clean_title,
                },
            })

        body_text = response.response

        # Format outbound payload adhering to WhatsApp Cloud API interactive message schema
        if buttons:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body_text},
                    "action": {"buttons": buttons},
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "text",
                "text": {"preview_url": True, "body": body_text},
            }

        return payload
