from app.adapters.base import BaseChannelAdapter
from app.adapters.voice_adapter import VoiceAdapter
from app.adapters.website_adapter import WebsiteAdapter
from app.adapters.whatsapp_adapter import WhatsAppAdapter
from app.schemas.channel import ChannelType

_ADAPTERS: dict[str, BaseChannelAdapter] = {
    ChannelType.WEBSITE.value: WebsiteAdapter(),
    ChannelType.WHATSAPP.value: WhatsAppAdapter(),
    ChannelType.VOICE.value: VoiceAdapter(),
}


def get_channel_adapter(channel: ChannelType | str) -> BaseChannelAdapter:
    """
    Returns the singleton adapter instance for the specified communication channel.
    """
    key = channel.value if isinstance(channel, ChannelType) else str(channel).lower()
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        # Default to website adapter for web/REST interactions
        return _ADAPTERS[ChannelType.WEBSITE.value]
    return adapter


__all__ = [
    "BaseChannelAdapter",
    "VoiceAdapter",
    "WebsiteAdapter",
    "WhatsAppAdapter",
    "get_channel_adapter",
]
