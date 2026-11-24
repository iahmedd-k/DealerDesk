from pydantic import BaseModel, Field


class TwilioInboundMessage(BaseModel):
    """
    Structured model for incoming WhatsApp webhook payload from Twilio.
    """
    from_number: str = Field(..., alias="From", description="Sender WhatsApp identifier, e.g., whatsapp:+1234567890")
    body: str = Field(..., alias="Body", description="Text content of the incoming WhatsApp message")
    to_number: str | None = Field(None, alias="To", description="Recipient Twilio WhatsApp number")
    message_sid: str | None = Field(None, alias="MessageSid", description="Unique identifier for the message assigned by Twilio")
    account_sid: str | None = Field(None, alias="AccountSid", description="Twilio Account SID")
    profile_name: str | None = Field(None, alias="ProfileName", description="Sender profile name on WhatsApp")
    wa_id: str | None = Field(None, alias="WaId", description="Sender phone number without whatsapp: prefix")
    num_media: int = Field(default=0, alias="NumMedia", description="Number of media files attached")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class WhatsAppOutboundMessage(BaseModel):
    """
    Structured model for sending an outbound WhatsApp message.
    """
    to: str = Field(..., description="Recipient phone number (with or without 'whatsapp:' prefix)")
    body: str = Field(..., description="Message text body")
    from_number: str | None = Field(None, description="Optional sender number override")
    media_urls: list[str] | None = Field(None, description="Optional media URLs to attach")
