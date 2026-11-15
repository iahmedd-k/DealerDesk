from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    admin_name: str = Field(min_length=1, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)


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


class StaffInvitationResponse(BaseModel):
    user_id: int
    email: EmailStr
    role: str
    expires_at: datetime
    delivery_status: str


class ActivationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class VehicleCreateRequest(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    model_year: int = Field(ge=1886, le=2200)
    variant: str | None = Field(default=None, max_length=120)
    description: str | None = None
    price: float = Field(ge=0)
    stock_number: str = Field(min_length=1, max_length=64)
    test_drive_enabled: bool = False


class VehicleResponse(VehicleCreateRequest):
    id: int
    dealership_id: int
    is_available: bool

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

    model_config = ConfigDict(from_attributes=True)
