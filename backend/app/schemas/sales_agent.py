from typing import Any
from pydantic import BaseModel, Field


class SalesAgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Customer message")
    conversation_id: int | None = Field(default=None, description="Existing persistent conversation ID if available")
    channel: str = Field(default="website", description="Inbound channel: website, whatsapp, voice")
    channel_user_id: str | None = Field(default=None, description="Channel user identifier (e.g. phone or session ID)")
    brand_id: int | None = Field(default=None, description="Optional brand filter")
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Optional client-side message history for stateless fallback",
    )


class SalesAgentChatResponse(BaseModel):
    response: str
    dealership_id: int
    dealership_name: str
    conversation_id: int | None = None
    intent: str
    suggested_actions: list[str] = Field(default_factory=list)
    matched_vehicles: list[dict[str, Any]] = Field(default_factory=list)
    available_slots: list[dict[str, Any]] = Field(default_factory=list)
    slot_hold: dict[str, Any] | None = None
    lead_created: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)
