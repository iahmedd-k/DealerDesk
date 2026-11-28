from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class ServiceAppointmentCreate(BaseModel):
    vehicle_id: int | None = None
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=32)
    scheduled_at: datetime
    concern: str = Field(min_length=1, max_length=4000)
    assigned_to_user_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("scheduled_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone")
        return value

    @field_validator("customer_name", "concern")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class ServiceAppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = None
    status: Literal["scheduled", "confirmed", "completed", "cancelled", "no_show"] | None = None
    assigned_to_user_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("scheduled_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("scheduled_at must include a timezone")
        return value


class ServiceAppointmentResponse(BaseModel):
    id: int
    dealership_id: int
    vehicle_id: int | None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    scheduled_at: datetime
    concern: str
    status: str
    assigned_to_user_id: int | None
    notes: str | None
    completed_at: datetime | None
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceWorkOrderCreate(BaseModel):
    appointment_id: int | None = None
    vehicle_id: int | None = None
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=32)
    concern: str = Field(min_length=1, max_length=4000)
    diagnosis: str | None = Field(default=None, max_length=4000)
    labor_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    parts_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    follow_up_at: datetime | None = None
    follow_up_status: Literal["not_required", "pending", "completed"] = "not_required"
    follow_up_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("customer_name", "concern")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("follow_up_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("follow_up_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_follow_up(self) -> "ServiceWorkOrderCreate":
        if self.follow_up_at is None and self.follow_up_status != "not_required":
            raise ValueError("follow_up_at is required when follow-up is enabled")
        if self.follow_up_at is not None and self.follow_up_status == "not_required":
            self.follow_up_status = "pending"
        return self


class ServiceWorkOrderUpdate(BaseModel):
    status: Literal["open", "in_progress", "completed", "cancelled"] | None = None
    diagnosis: str | None = Field(default=None, max_length=4000)
    labor_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    parts_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    follow_up_at: datetime | None = None
    follow_up_status: Literal["not_required", "pending", "completed"] | None = None
    follow_up_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("follow_up_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("follow_up_at must include a timezone")
        return value


class ServiceWorkOrderResponse(BaseModel):
    id: int
    dealership_id: int
    appointment_id: int | None
    vehicle_id: int | None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    concern: str
    diagnosis: str | None
    status: str
    labor_cost: float
    parts_cost: float
    total_cost: float
    follow_up_at: datetime | None
    follow_up_status: str
    follow_up_notes: str | None
    created_by_user_id: int | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleWarrantyCreate(BaseModel):
    vehicle_id: int
    provider: str = Field(min_length=1, max_length=150)
    policy_number: str | None = Field(default=None, max_length=100)
    coverage: str = Field(min_length=1, max_length=4000)
    start_date: date
    end_date: date
    mileage_limit: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("provider", "coverage")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> "VehicleWarrantyCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class VehicleWarrantyUpdate(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=150)
    policy_number: str | None = Field(default=None, max_length=100)
    coverage: str | None = Field(default=None, min_length=1, max_length=4000)
    start_date: date | None = None
    end_date: date | None = None
    mileage_limit: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("provider", "coverage")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class VehicleWarrantyResponse(BaseModel):
    id: int
    dealership_id: int
    vehicle_id: int
    provider: str
    policy_number: str | None
    coverage: str
    start_date: date
    end_date: date
    mileage_limit: int | None
    notes: str | None
    created_by_user_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_active(self) -> bool:
        today = date.today()
        return self.start_date <= today <= self.end_date
