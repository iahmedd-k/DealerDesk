from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadQuoteCreate(BaseModel):
    vehicle_id: int | None = None
    vehicle_label: str | None = Field(default=None, max_length=200)
    sale_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    trade_in_vehicle: str | None = Field(default=None, max_length=200)
    trade_in_value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    down_payment: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    apr_percent: Decimal = Field(ge=0, le=50, max_digits=5, decimal_places=2)
    loan_term_months: int = Field(ge=1, le=120)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("vehicle_label", "trade_in_vehicle", "notes")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class LeadQuoteStatusUpdate(BaseModel):
    status: Literal["sent", "accepted", "declined", "expired"]


class LeadQuoteResponse(BaseModel):
    id: int
    dealership_id: int
    lead_id: int
    version: int
    status: Literal["draft", "sent", "accepted", "declined", "expired"]
    vehicle_id: int | None
    vehicle_label: str | None
    sale_price: float
    trade_in_vehicle: str | None
    trade_in_value: float
    down_payment: float
    amount_financed: float
    apr_percent: float
    loan_term_months: int
    estimated_monthly_payment: float
    disclaimer: str
    notes: str | None
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
