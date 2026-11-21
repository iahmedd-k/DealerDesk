from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[int | None] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), default="ready")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(JSON)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Dealership(Base):
    __tablename__ = "dealerships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_plan: Mapped[str] = mapped_column(String(32), default="pro")
    subscription_status: Mapped[str] = mapped_column(String(32), default="active")
    monthly_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("499.00")
    )
    max_brands: Mapped[int] = mapped_column(Integer, default=10)
    max_vehicles: Mapped[int] = mapped_column(Integer, default=250)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


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
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (
        Index(
            "uq_brand_dealership_name_active",
            "dealership_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    logo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint(
            "dealership_id", "stock_number", name="uq_vehicle_dealership_stock"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"), index=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey(
            "brands.id", name="fk_vehicles_brand_id_brands", ondelete="RESTRICT"
        ),
        index=True,
    )
    make: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    model_year: Mapped[int] = mapped_column(Integer)
    variant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    stock_number: Mapped[str] = mapped_column(String(64))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    test_drive_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    images: Mapped[list["VehicleImage"]] = relationship(
        back_populates="vehicle",
        order_by="VehicleImage.position",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class VehicleImage(Base):
    __tablename__ = "vehicle_images"
    __table_args__ = (
        UniqueConstraint(
            "storage_path",
            name="uq_vehicle_images_storage_path",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    storage_path: Mapped[str] = mapped_column(String(512))
    public_url: Mapped[str] = mapped_column(String(1024))
    media_type: Mapped[str] = mapped_column(String(32))
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    vehicle: Mapped[Vehicle] = relationship(back_populates="images")


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


class TestDriveBooking(Base):
    __tablename__ = "test_drive_bookings"
    __table_args__ = (
        Index(
            "uq_test_drive_booking_active_customer",
            "slot_id",
            "customer_id",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("test_drive_slots.id"), index=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="booked")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[customer_id],
        lazy="selectin",
    )
    slot: Mapped[TestDriveSlot] = relationship(
        TestDriveSlot,
        foreign_keys=[slot_id],
        lazy="selectin",
    )
    vehicle: Mapped[Vehicle] = relationship(
        Vehicle,
        foreign_keys=[vehicle_id],
        lazy="selectin",
    )

    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer else None

    @property
    def customer_email(self) -> str | None:
        return self.customer.email if self.customer else None

    @property
    def vehicle_name(self) -> str | None:
        if self.vehicle is None:
            return None
        return f"{self.vehicle.model_year} {self.vehicle.make} {self.vehicle.model}"

    @property
    def starts_at(self) -> datetime | None:
        return self.slot.starts_at if self.slot else None

    @property
    def ends_at(self) -> datetime | None:
        return self.slot.ends_at if self.slot else None


class CustomerLead(Base):
    __tablename__ = "customer_leads"
    __table_args__ = (
        Index("ix_customer_leads_dealership_status", "dealership_id", "status"),
        Index(
            "ix_customer_leads_dealership_assignee",
            "dealership_id",
            "assigned_to_user_id",
        ),
        UniqueConstraint(
            "test_drive_booking_id",
            name="uq_customer_leads_test_drive_booking",
        ),
        CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'test_drive_scheduled', "
            "'won', 'lost', 'follow_up')",
            name="ck_customer_leads_status",
        ),
        CheckConstraint(
            "NOT consent_to_contact OR consented_at IS NOT NULL",
            name="ck_customer_leads_consent_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    test_drive_booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_drive_bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24), default="website")
    status: Mapped[str] = mapped_column(String(24), default="new")
    consent_to_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
