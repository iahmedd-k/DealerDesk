from typing import Any
from app.adapters.base import BaseChannelAdapter
from app.schemas.channel import ChannelEvent, ChannelType
from app.schemas.sales_agent import SalesAgentChatResponse


class WebsiteAdapter(BaseChannelAdapter):
    """
    Website Chatbot Adapter.
    Handles web widget communication, rich JSON formatting, vehicle card previews,
    and interactive suggested action pills.
    """

    channel_type = ChannelType.WEBSITE

    def parse_inbound(
        self,
        dealership_id: int,
        payload: dict[str, Any] | str,
        headers: dict[str, str] | None = None,
    ) -> ChannelEvent:
        if isinstance(payload, str):
            message_text = payload
            session_id = "web-anonymous"
            metadata: dict[str, Any] = {}
        else:
            message_text = payload.get("message", "")
            session_id = payload.get("channel_user_id") or payload.get("session_id") or "web-anonymous"
            metadata = {
                "conversation_id": payload.get("conversation_id"),
                "brand_id": payload.get("brand_id"),
                "user_agent": (headers or {}).get("user-agent"),
            }

        return ChannelEvent(
            dealership_id=dealership_id,
            channel=self.channel_type,
            channel_user_id=session_id,
            message=message_text,
            metadata=metadata,
        )

    def format_outbound(
        self,
        response: SalesAgentChatResponse,
        recipient: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "channel": "website",
            "session_id": recipient,
            "conversation_id": response.conversation_id,
            "text": response.response,
            "intent": response.intent,
            "cards": [
                {
                    "type": "vehicle",
                    "id": v.get("id"),
                    "title": f"{v.get('model_year')} {v.get('make')} {v.get('model')}",
                    "price": v.get("price"),
                    "image_url": v.get("primary_image_url"),
                    "stock_number": v.get("stock_number"),
                    "test_drive_enabled": v.get("test_drive_enabled", True),
                }
                for v in response.matched_vehicles
            ],
            "slots": response.available_slots,
            "actions": [
                {"label": action, "type": "quick_reply"}
                for action in response.suggested_actions
            ],
            "slot_hold": response.slot_hold,
            "lead_created": response.lead_created,
        }

    def verify_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        # Website chatbot communicates via standard authenticated / public CORS APIs
        return True
