from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="Customer message or inquiry")
    brand_id: int | None = Field(default=None, ge=1, description="Optional brand filter for multi-brand dealerships")
    conversation_history: list[AssistantMessage] = Field(
        default_factory=list,
        max_length=12,
        description="Previous conversation turns for context continuity",
    )
    channel: Literal["website", "whatsapp", "api"] = "website"


class AssistantSource(BaseModel):
    document_id: int
    filename: str
    page_number: int | None = None
    snippet: str
    score: float


class AssistantVehicleMatch(BaseModel):
    id: int
    make: str
    model: str
    model_year: int
    price: float
    stock_number: str
    test_drive_enabled: bool
    is_available: bool


class AssistantSlotMatch(BaseModel):
    id: int
    vehicle_id: int
    starts_at: datetime
    ends_at: datetime
    remaining_capacity: int


class AssistantChatResponse(BaseModel):
    response: str
    dealership_id: int
    dealership_name: str
    brand_id: int | None = None
    intent: str
    sources: list[AssistantSource] = Field(default_factory=list)
    matched_vehicles: list[AssistantVehicleMatch] = Field(default_factory=list)
    available_slots: list[AssistantSlotMatch] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
