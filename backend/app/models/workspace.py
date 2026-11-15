from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dealership(Base):
    __tablename__ = "dealerships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class StaffInvitation(Base):
    __tablename__ = "staff_invitations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"), index=True)
    invited_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(32))
    activation_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("dealership_id", "stock_number", name="uq_vehicle_dealership_stock"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"), index=True)
    make: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    model_year: Mapped[int] = mapped_column(Integer)
    variant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column()
    stock_number: Mapped[str] = mapped_column(String(64))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    test_drive_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class TestDriveSettings(Base):
    __tablename__ = "test_drive_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id"), unique=True, index=True
    )
    opening_time: Mapped[str] = mapped_column(String(5), default="09:00")
    closing_time: Mapped[str] = mapped_column(String(5), default="17:00")
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    capacity_per_slot: Mapped[int] = mapped_column(Integer, default=1)
    days_open: Mapped[str] = mapped_column(String(32), default="0,1,2,3,4")


class TestDriveSlot(Base):
    __tablename__ = "test_drive_slots"
    __table_args__ = (
        UniqueConstraint(
            "dealership_id",
            "vehicle_id",
            "starts_at",
            name="uq_test_drive_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    booked_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
