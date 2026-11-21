from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
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
    logo_url: str | None
    is_active: bool
    is_deleted: bool

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


class VehicleCreateRequest(BaseModel):
    brand_id: int = Field(ge=1)
    model: str = Field(min_length=1, max_length=80)
    model_year: int = Field(ge=1886, le=2200)
    variant: str | None = Field(default=None, max_length=120)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    stock_number: str = Field(min_length=1, max_length=64)
    test_drive_enabled: bool = False

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
    is_available: bool
    price: float
    images: list[VehicleImageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


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
    stock_number: str | None = Field(default=None, min_length=1, max_length=64)
    is_available: bool | None = None
    test_drive_enabled: bool | None = None


class DealershipUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

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

    model_config = ConfigDict(from_attributes=True)


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


class TestDriveSlotUpdateRequest(BaseModel):
    is_active: bool


class TestDriveBookingRequest(BaseModel):
    confirmed: bool = Field(
        default=True,
        description="Explicit customer confirmation to book the slot",
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
    status: str
    created_at: datetime
    cancelled_at: datetime | None

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
