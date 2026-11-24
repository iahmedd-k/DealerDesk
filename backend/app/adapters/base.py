from abc import ABC, abstractmethod
from typing import Any
from app.schemas.channel import ChannelEvent, ChannelType
from app.schemas.sales_agent import SalesAgentChatResponse


class BaseChannelAdapter(ABC):
    """
    Abstract interface for channel adapters.
    Each adapter isolates channel-specific wire protocols, normalizes incoming
    payloads into unified ChannelEvents, and formats agent responses into
    channel-native presentations.
    """

    channel_type: ChannelType

    @abstractmethod
    def parse_inbound(
        self,
        dealership_id: int,
        payload: dict[str, Any] | str,
        headers: dict[str, str] | None = None,
    ) -> ChannelEvent:
        """
        Parses and normalizes channel-specific incoming data into a standard ChannelEvent.
        """
        pass

    @abstractmethod
    def format_outbound(
        self,
        response: SalesAgentChatResponse,
        recipient: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Converts the standard SalesAgentChatResponse into the channel-specific delivery format.
        """
        pass

    @abstractmethod
    def verify_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Validates webhook authenticity (e.g. HMAC-SHA256 signature).
        """
        pass
