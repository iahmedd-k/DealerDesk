from datetime import datetime
from decimal import Decimal
from enum import Enum
import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    model_validator,
    field_validator,
)


STAFF_ROLES = {"dealership_admin", "manager", "sales_rep"}


class CustomerSignUpRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class DealershipRegistrationRequest(BaseModel):
    dealership_name: str = Field(min_length=1, max_length=150)
    dealership_email: EmailStr
    dealership_phone: str | None = Field(default=None, max_length=32)
    dealership_address: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    brands: list[str] = Field(min_length=1, max_length=20)
    admin_name: str = Field(min_length=1, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("brands")
    @classmethod
    def validate_brands(cls, value: list[str]) -> list[str]:
        cleaned = [name.strip() for name in value]
        if any(not name or len(name) > 100 for name in cleaned):
            raise ValueError("brand names must contain 1 to 100 characters")
        if len({name.casefold() for name in cleaned}) != len(cleaned):
            raise ValueError("brand names cannot contain duplicates")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dealership_name": "Apex Motors NYC",
                "dealership_email": "contact@apexmotors.com",
                "dealership_phone": "+1-212-555-0199",
                "dealership_address": "450 W 33rd St, New York, NY 10001",
                "timezone": "America/New_York",
                "brands": ["Toyota", "BMW", "Audi"],
                "admin_name": "Marcus Vance",
                "admin_email": "marcus@apexmotors.com",
                "admin_password": "SecurePassword!123",
            }
        }
    )


class BrandCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("brand name cannot be blank")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Porsche",
            }
        }
    )


class BrandUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("brand name cannot be blank")
        return value


class BrandResponse(BaseModel):
    id: int
    dealership_id: int
    name: str
    logo_url: str | None = None
    is_active: bool
    is_deleted: bool
    vehicles_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class StaffInvitationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in STAFF_ROLES - {"dealership_admin"}:
            raise ValueError("role must be manager or sales_rep")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jane Sales",
                "email": "jane@apexmotors.com",
                "role": "sales_rep",
            }
        }
    )


class StaffInvitationResponse(BaseModel):
    id: int | None = None
    user_id: int
    email: EmailStr
    role: str
    expires_at: datetime
    delivery_status: str
    status: str = "pending"


class ActivationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    IN_TRANSIT = "in_transit"
    UNAVAILABLE = "unavailable"


class VehicleStatusTransitionRequest(BaseModel):
    status: str = Field(description="New status: available, reserved, sold, in_transit, unavailable")
    notes: str | None = Field(default=None, max_length=500, description="Optional notes explaining the transition")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"available", "reserved", "sold", "in_transit", "unavailable"}
        cleaned = value.strip().lower()
        if cleaned not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return cleaned


class VehicleStatusHistoryResponse(BaseModel):
    id: int
    dealership_id: int
    vehicle_id: int
    changed_by_user_id: int | None = None
    changed_by_user_email: str | None = None
    previous_status: str
    new_status: str
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleCreateRequest(BaseModel):
    brand_id: int = Field(ge=1)
    model: str = Field(min_length=1, max_length=80)
    model_year: int = Field(ge=1886, le=2200)
    variant: str | None = Field(default=None, max_length=120)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    acquisition_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    location: str | None = Field(default=None, max_length=100)
    reconditioning_status: Literal[
        "not_required", "needed", "in_progress", "complete"
    ] = "not_required"
    acquired_at: datetime | None = None
    stock_number: str = Field(min_length=1, max_length=64)
    vin: str | None = Field(default=None, max_length=17)
    mileage: int | None = Field(default=None, ge=0, le=2_000_000)
    transmission: str | None = Field(default=None, max_length=32)
    fuel_type: str | None = Field(default=None, max_length=32)
    drivetrain: str | None = Field(default=None, max_length=32)
    exterior_color: str | None = Field(default=None, max_length=64)
    interior_color: str | None = Field(default=None, max_length=64)
    status: str = Field(default="available", description="Vehicle lifecycle status: available, reserved, sold, in_transit, unavailable")
    test_drive_enabled: bool = False

    @field_validator("status")
    @classmethod
    def validate_vehicle_status(cls, value: str) -> str:
        allowed = {"available", "reserved", "sold", "in_transit", "unavailable"}
        cleaned = value.strip().lower()
        if cleaned not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return cleaned

    @field_validator("vin")
    @classmethod
    def normalize_vin(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().upper()
        if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", cleaned):
            raise ValueError("VIN must contain 17 valid letters or digits")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "brand_id": 1,
                "model": "Camry",
                "model_year": 2024,
                "variant": "XSE V6",
                "description": "Sport-tuned suspension, panoramic glass roof, 9-inch multimedia display.",
                "price": 36500.0,
                "stock_number": "STK-2024-001",
                "status": "available",
                "test_drive_enabled": True,
            }
        }
    )


class VehicleImageResponse(BaseModel):
    id: int
    vehicle_id: int
    public_url: str
    media_type: str
    alt_text: str | None
    position: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleResponse(VehicleCreateRequest):
    id: int
    dealership_id: int
    make: str
    status: str = "available"
    is_available: bool
    price: float
    images: list[VehicleImageResponse] = Field(default_factory=list)
    acquisition_cost: Decimal | None = Field(default=None, exclude=True)
    location: str | None = Field(default=None, exclude=True)
    reconditioning_status: str = Field(default="not_required", exclude=True)
    acquired_at: datetime | None = Field(default=None, exclude=True)
    days_in_stock: int | None = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)


class VehicleStaffResponse(VehicleResponse):
    acquisition_cost: Decimal | None = None
    location: str | None = None
    reconditioning_status: str = "not_required"
    acquired_at: datetime | None = None
    days_in_stock: int | None = None


class VehicleImageUpdateRequest(BaseModel):
    position: int | None = Field(default=None, ge=0)
    alt_text: str | None = Field(default=None, max_length=255)


class VehicleUpdateRequest(BaseModel):
    brand_id: int | None = Field(default=None, ge=1)
    model: str | None = Field(default=None, min_length=1, max_length=80)
    model_year: int | None = Field(default=None, ge=1886, le=2200)
    variant: str | None = Field(default=None, max_length=120)
    description: str | None = None
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    acquisition_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    location: str | None = Field(default=None, max_length=100)
    reconditioning_status: Literal[
        "not_required", "needed", "in_progress", "complete"
    ] | None = None
    acquired_at: datetime | None = None
    stock_number: str | None = Field(default=None, min_length=1, max_length=64)
    vin: str | None = Field(default=None, max_length=17)
    mileage: int | None = Field(default=None, ge=0, le=2_000_000)
    transmission: str | None = Field(default=None, max_length=32)
    fuel_type: str | None = Field(default=None, max_length=32)
    drivetrain: str | None = Field(default=None, max_length=32)
    exterior_color: str | None = Field(default=None, max_length=64)
    interior_color: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, description="Vehicle lifecycle status")
    is_available: bool | None = None
    test_drive_enabled: bool | None = None

    @field_validator("status")
    @classmethod
    def validate_update_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"available", "reserved", "sold", "in_transit", "unavailable"}
        cleaned = value.strip().lower()
        if cleaned not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return cleaned

    @field_validator("vin")
    @classmethod
    def validate_update_vin(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().upper()
        if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", cleaned):
            raise ValueError("VIN must contain 17 valid letters or digits")
        return cleaned


class CSVVehicleImportRequest(BaseModel):
    csv_content: str = Field(min_length=1, max_length=2_000_000)
    mode: Literal["create", "upsert"] = "create"


class DealershipUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    whatsapp_number: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("whatsapp_number")
    @classmethod
    def validate_whatsapp_number(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().removeprefix("whatsapp:")
        if not re.fullmatch(r"\+[1-9]\d{7,14}", cleaned):
            raise ValueError("whatsapp_number must be an E.164 number, such as +14155550123")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def validate_update_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class DealershipResponse(DealershipUpdateRequest):
    id: int
    is_active: bool
    subscription_plan: str = "pro"
    subscription_status: str = "active"
    monthly_price: float = 499.0
    max_brands: int = 10
    max_vehicles: int = 250
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DealershipDetailedResponse(DealershipResponse):
    brands_count: int = 0
    vehicles_count: int = 0
    staff_count: int = 0


class DealershipSubscriptionUpdateRequest(BaseModel):
    subscription_plan: str | None = Field(default=None)
    subscription_status: str | None = Field(default=None)
    monthly_price: Decimal | None = Field(default=None, ge=0)
    max_brands: int | None = Field(default=None, ge=1)
    max_vehicles: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class PlatformMetricsResponse(BaseModel):
    total_dealerships: int
    active_dealerships: int
    total_mrr: float
    total_vehicles: int
    total_bookings: int
    total_staff: int
    total_brands: int
    plan_distribution: dict[str, int]


class StaffUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_update_role(cls, value: str | None) -> str | None:
        if value is not None and value not in STAFF_ROLES - {"dealership_admin"}:
            raise ValueError("role must be manager or sales_rep")
        return value


class TestDriveSlotCreateRequest(BaseModel):
    vehicle_id: int = Field(ge=1)
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(default=1, ge=1, le=20)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_slot_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Slot timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_slot_range(self) -> "TestDriveSlotCreateRequest":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class TestDriveSlotUpdateRequest(BaseModel):
    is_active: bool | None = None
    capacity: int | None = Field(default=None, ge=1, le=20)

    @model_validator(mode="after")
    def validate_any_field(self) -> "TestDriveSlotUpdateRequest":
        if self.is_active is None and self.capacity is None:
            raise ValueError("Provide is_active or capacity to update")
        return self


class TestDriveBookingRequest(BaseModel):
    confirmed: bool = Field(
        ...,
        description="Explicit customer confirmation to book the slot",
    )
    hold_token: str | None = Field(
        default=None,
        description="Optional pre-existing slot reservation hold token",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confirmed": True,
            }
        }
    )


class TestDriveRescheduleRequest(BaseModel):
    new_slot_id: int
    verification_email: str | None = Field(
        default=None,
        description="Customer email for contact/identity verification",
    )
    verification_phone: str | None = Field(
        default=None,
        description="Customer phone for contact/identity verification",
    )
    confirmed: bool = Field(
        default=True,
        description="Explicit confirmation to reschedule",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_slot_id": 42,
                "verification_email": "customer@example.com",
                "confirmed": True,
            }
        }
    )


class TestDriveCancellationRequest(BaseModel):
    verification_email: str | None = Field(
        default=None,
        description="Customer email for contact/identity verification",
    )
    verification_phone: str | None = Field(
        default=None,
        description="Customer phone for contact/identity verification",
    )
    reason: str | None = Field(
        default=None,
        max_length=255,
        description="Reason for cancellation",
    )


class TestDriveBookingResponse(BaseModel):
    id: int
    slot_id: int
    dealership_id: int
    vehicle_id: int
    customer_id: int
    customer_name: str | None = None
    customer_email: EmailStr | None = None
    vehicle_name: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str
    assigned_to_user_id: int | None = None
    outcome_at: datetime | None = None
    outcome_notes: str | None = None
    created_at: datetime
    cancelled_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TestDriveBookingOutcomeRequest(BaseModel):
    status: Literal["completed", "no_show"] | None = None
    assigned_to_user_id: int | None = Field(default=None, ge=1)
    outcome_notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_changes(self) -> "TestDriveBookingOutcomeRequest":
        if not ({"status", "assigned_to_user_id", "outcome_notes"} & self.model_fields_set):
            raise ValueError("Provide a booking outcome, host, or outcome note")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Booking outcome cannot be null")
        return self


class CustomerLeadCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    message: str = Field(min_length=1, max_length=2000)
    source: Literal["website", "assistant", "phone", "walk_in", "referral", "whatsapp", "voice"] = "website"
    requested_vehicle_id: int | None = Field(default=None, ge=1)
    consent_to_contact: Literal[True]
    email_consent: bool = False
    sms_consent: bool = False
    whatsapp_consent: bool = False
    budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    purchase_timeline: str | None = Field(default=None, max_length=64)
    conversation_id: int | None = Field(default=None, ge=1)
    preferences: dict | None = None
    auto_assign: bool = False

    @field_validator("name", "message")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            return value or None
        return value


class CustomerLeadUpdateRequest(BaseModel):
    status: Literal[
        "new",
        "contacted",
        "qualified",
        "test_drive_scheduled",
        "won",
        "lost",
        "follow_up",
    ] | None = None
    lost_reason: Literal[
        "price",
        "vehicle_unavailable",
        "bought_elsewhere",
        "financing",
        "timing",
        "no_response",
        "other",
    ] | None = None
    email_consent: bool = False
    sms_consent: bool = False
    whatsapp_consent: bool = False
    assigned_to_user_id: int | None = Field(default=None, ge=1)
    next_follow_up_at: datetime | None = None
    budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    purchase_timeline: str | None = Field(default=None, max_length=64)
    preferences: dict | None = None
    deal_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    deal_notes: str | None = Field(default=None, max_length=2000)
    trade_in_vehicle: str | None = Field(default=None, max_length=200)
    trade_in_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    down_payment: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    apr_percent: Decimal | None = Field(default=None, ge=0, le=50, max_digits=5, decimal_places=2)
    loan_term_months: int | None = Field(default=None, ge=1, le=120)

    @field_validator("next_follow_up_at")
    @classmethod
    def validate_follow_up_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("next_follow_up_at must include a timezone")
        return value


class BulkCustomerLeadUpdateRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1, max_length=200)
    status: Literal["new", "contacted", "qualified", "follow_up"] | None = None
    assigned_to_user_id: int | None = Field(default=None, ge=1)

    @field_validator("lead_ids")
    @classmethod
    def validate_unique_lead_ids(cls, value: list[int]) -> list[int]:
        if any(lead_id < 1 for lead_id in value):
            raise ValueError("lead_ids must contain positive IDs")
        if len(set(value)) != len(value):
            raise ValueError("lead_ids cannot contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_update_fields(self) -> "BulkCustomerLeadUpdateRequest":
        if not ({"status", "assigned_to_user_id"} & self.model_fields_set):
            raise ValueError("Provide a status and/or assigned_to_user_id")
        return self


class CSVLeadImportRequest(BaseModel):
    csv_content: str = Field(min_length=1, max_length=2_000_000)


class CustomerLeadConvertRequest(BaseModel):
    booking_id: int = Field(ge=1)


class CustomerLeadResponse(BaseModel):
    id: int
    dealership_id: int
    customer_id: int | None
    requested_vehicle_id: int | None
    assigned_to_user_id: int | None
    test_drive_booking_id: int | None
    name: str
    email: EmailStr
    phone: str | None
    message: str
    source: str
    status: Literal[
        "new",
        "contacted",
        "qualified",
        "test_drive_scheduled",
        "won",
        "lost",
        "follow_up",
    ]
    consent_to_contact: bool
    consented_at: datetime | None
    email_consent: bool
    email_consented_at: datetime | None
    email_opted_out_at: datetime | None
    sms_consent: bool
    sms_consented_at: datetime | None
    sms_opted_out_at: datetime | None
    whatsapp_consent: bool
    whatsapp_consented_at: datetime | None
    whatsapp_opted_out_at: datetime | None
    lost_reason: str | None = None
    next_follow_up_at: datetime | None
    budget: float | None = None
    purchase_timeline: str | None = None
    conversation_id: int | None = None
    preferences: dict | None = None
    deal_value: float | None = None
    deal_notes: str | None = None
    trade_in_vehicle: str | None = None
    trade_in_value: float | None = None
    down_payment: float | None = None
    apr_percent: float | None = None
    loan_term_months: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadActivityCreateRequest(BaseModel):
    activity_type: Literal["note", "call", "email", "meeting", "quote"] = "note"
    summary: str = Field(min_length=1, max_length=2000)
    details: dict | None = None


class LeadActivityResponse(BaseModel):
    id: int
    dealership_id: int
    lead_id: int
    actor_user_id: int | None = None
    actor_user_email: str | None = None
    activity_type: str
    summary: str
    details: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestDriveSettingsRequest(BaseModel):
    opening_time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    closing_time: str = Field(default="17:00", pattern=r"^\d{2}:\d{2}$")
    slot_duration_minutes: int = Field(default=30, ge=15, le=240)
    capacity_per_slot: int = Field(default=1, ge=1, le=100)
    days_open: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])

    @field_validator("opening_time", "closing_time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("time must be between 00:00 and 23:59")
        return value

    @field_validator("days_open")
    @classmethod
    def validate_days(cls, value: list[int]) -> list[int]:
        if not value or any(day < 0 or day > 6 for day in value):
            raise ValueError("days_open must contain weekdays from 0 to 6")
        if len(set(value)) != len(value):
            raise ValueError("days_open cannot contain duplicates")
        return sorted(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "opening_time": "09:00",
                "closing_time": "18:00",
                "slot_duration_minutes": 30,
                "capacity_per_slot": 2,
                "days_open": [0, 1, 2, 3, 4, 5],
            }
        }
    )


class TestDriveSettingsResponse(TestDriveSettingsRequest):
    id: int
    dealership_id: int

    model_config = ConfigDict(from_attributes=True)

    @field_validator("days_open", mode="before")
    @classmethod
    def parse_days_open(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, str):
            return [int(day) for day in value.split(",") if day]
        return value


class TestDriveSlotResponse(BaseModel):
    id: int
    vehicle_id: int
    starts_at: datetime
    ends_at: datetime
    capacity: int
    booked_count: int
    is_active: bool

    @computed_field
    @property
    def remaining_capacity(self) -> int:
        return max(0, self.capacity - self.booked_count)

    @computed_field
    @property
    def is_available(self) -> bool:
        return self.is_active and (self.capacity - self.booked_count) > 0

    model_config = ConfigDict(from_attributes=True)
