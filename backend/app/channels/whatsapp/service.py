import logging
from functools import lru_cache
from typing import Any

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import get_settings

logger = logging.getLogger("dealerdesk.channels.whatsapp")


class TwilioWhatsAppService:
    """
    Service responsible for interacting with the Twilio WhatsApp API:
    - Generating TwiML replies for synchronous webhook responses
    - Sending outbound proactive messages via Twilio REST API
    """

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ) -> None:
        settings = get_settings()
        self.account_sid = account_sid or (
            settings.twilio_account_sid.get_secret_value()
            if settings.twilio_account_sid
            else None
        )
        self.auth_token = auth_token or (
            settings.twilio_auth_token.get_secret_value()
            if settings.twilio_auth_token
            else None
        )
        self.from_number = from_number or settings.twilio_whatsapp_from

        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            if not self.account_sid or not self.auth_token:
                raise ValueError(
                    "Twilio credentials (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) are not configured."
                )
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    @staticmethod
    def create_twiml_reply(message_body: str) -> str:
        """
        Creates a TwiML MessagingResponse XML string to reply synchronously to a webhook.
        """
        twiml = MessagingResponse()
        twiml.message(message_body)
        return str(twiml)

    def send_message(
        self,
        to: str,
        body: str,
        from_override: str | None = None,
        media_urls: list[str] | None = None,
        status_callback: str | None = None,
    ) -> dict[str, Any]:
        """
        Sends an outbound WhatsApp message using the Twilio REST API.
        """
        sender = from_override or self.from_number
        if not sender.startswith("whatsapp:"):
            sender = f"whatsapp:{sender}"

        recipient = to if to.startswith("whatsapp:") else f"whatsapp:{to}"

        try:
            if status_callback is None:
                status_callback = get_settings().twilio_status_callback_url
            logger.info("Sending Twilio WhatsApp message")
            kwargs: dict[str, Any] = {
                "from_": sender,
                "to": recipient,
                "body": body,
            }
            if media_urls:
                kwargs["media_url"] = media_urls
            if status_callback:
                kwargs["status_callback"] = status_callback

            msg = self.client.messages.create(**kwargs)
            logger.info("Twilio WhatsApp message accepted. SID: %s", msg.sid)
            return {
                "sid": msg.sid,
                "status": msg.status,
                "to": recipient,
                "from": sender,
            }
        except TwilioRestException as exc:
            logger.error(
                "Twilio API rejected WhatsApp message (code=%s, status=%s)",
                exc.code,
                exc.status,
            )
            raise


@lru_cache
def get_whatsapp_service() -> TwilioWhatsAppService:
    return TwilioWhatsAppService()
