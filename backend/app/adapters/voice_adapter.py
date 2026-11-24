import hmac
import hashlib
import base64
import re
from typing import Any
from urllib.parse import urlencode

from app.adapters.base import BaseChannelAdapter
from app.schemas.channel import ChannelEvent, ChannelType
from app.schemas.sales_agent import SalesAgentChatResponse


class VoiceAdapter(BaseChannelAdapter):
    """
    Voice Telephony Adapter (Twilio Voice / LiveKit / Telnyx).
    Normalizes speech-to-text transcripts, prepares natural spoken audio prompts,
    formats telephony TwiML with barge-in support, and validates webhook signatures.
    """

    channel_type = ChannelType.VOICE

    def verify_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Validates telephony webhook authenticity.
        """
        if not signature or not secret:
            return False
        # Constant-time comparison for telephony auth tokens
        expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha1).digest()
        expected_sig = base64.b64encode(expected).decode("utf-8")
        return hmac.compare_digest(expected_sig, signature)

    def parse_inbound(
        self,
        dealership_id: int,
        payload: dict[str, Any] | str,
        headers: dict[str, str] | None = None,
    ) -> ChannelEvent:
        """
        Extracts spoken caller transcript and caller phone number from telephony webhook.
        """
        if isinstance(payload, str):
            return ChannelEvent(
                dealership_id=dealership_id,
                channel=self.channel_type,
                channel_user_id="caller-unknown",
                message=payload,
            )

        caller_phone = payload.get("From") or payload.get("caller") or payload.get("channel_user_id") or "caller-unknown"
        call_sid = payload.get("CallSid") or payload.get("call_id") or ""

        # Speech recognition transcript (from Twilio <Gather> or live STT engine)
        spoken_text = (
            payload.get("SpeechResult")
            or payload.get("transcript")
            or payload.get("message")
            or payload.get("Digits")
            or "Hello"
        )

        confidence = payload.get("Confidence")
        return ChannelEvent(
            dealership_id=dealership_id,
            channel=self.channel_type,
            channel_user_id=str(caller_phone),
            message=str(spoken_text),
            metadata={
                "call_sid": call_sid,
                "confidence": float(confidence) if confidence else None,
                "call_status": payload.get("CallStatus", "in-progress"),
            },
        )

    def format_outbound(
        self,
        response: SalesAgentChatResponse,
        recipient: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Prepares the spoken audio script and TwiML XML response.
        """
        spoken_script = self.sanitize_for_speech(response.response)
        action_url = (context or {}).get("action_url", "/api/v1/dealerships/voice/webhook")

        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Gather input="speech" timeout="4" speechTimeout="auto" action="{action_url}" method="POST">\n'
            f'        <Say voice="Polly.Joanna-Neural" language="en-US">{spoken_script}</Say>\n'
            "    </Gather>\n"
            f'    <Say voice="Polly.Joanna-Neural" language="en-US">Thank you for calling. Have a great day!</Say>\n'
            "    <Hangup/>\n"
            "</Response>"
        )

        return {
            "channel": "voice",
            "caller": recipient,
            "spoken_text": spoken_script,
            "twiml": twiml,
            "intent": response.intent,
        }

    @staticmethod
    def sanitize_for_speech(text: str) -> str:
        """
        Converts text and markdown into clean, natural spoken sentences.
        Strips asterisks, links, table markers, and verbalizes prices for natural pronunciation.
        """
        # Remove bold, italics, bullet points, and markdown links
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        clean = re.sub(r"[-*]\s+", "", clean)
        clean = re.sub(r"#+\s*", "", clean)

        # Convert currency figures like $28,000 into spoken text
        def _verbalize_price(match: re.Match) -> str:
            val_str = match.group(1).replace(",", "")
            try:
                val = int(val_str)
                if val >= 1000 and val % 1000 == 0:
                    thousands = val // 1000
                    return f"{thousands} thousand dollars"
                return f"{val} dollars"
            except ValueError:
                return f"{val_str} dollars"

        clean = re.sub(r"\$(\d{1,3}(?:,\d{3})+|\d+)", _verbalize_price, clean)

        # Remove extra whitespace and ensure voice turn brevity (max ~150 words)
        words = clean.split()
        if len(words) > 140:
            clean = " ".join(words[:140]) + ". Would you like more details or shall we schedule a test drive?"

        return clean.strip()
