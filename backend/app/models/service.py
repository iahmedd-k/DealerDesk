from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceAppointment(Base):
    __tablename__ = "service_appointments"
    __table_args__ = (
        Index(
            "ix_service_appointments_dealership_scheduled",
            "dealership_id",
            "scheduled_at",
        ),
        Index(
            "ix_service_appointments_dealership_status",
            "dealership_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    concern: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ServiceWorkOrder(Base):
    __tablename__ = "service_work_orders"
    __table_args__ = (
        UniqueConstraint(
            "appointment_id",
            name="uq_service_work_orders_appointment",
        ),
        Index(
            "ix_service_work_orders_dealership_status",
            "dealership_id",
            "status",
        ),
        Index(
            "ix_service_work_orders_follow_up",
            "dealership_id",
            "follow_up_at",
            "follow_up_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    concern: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open")
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    parts_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    follow_up_status: Mapped[str] = mapped_column(String(24), default="not_required")
    follow_up_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def total_cost(self) -> Decimal:
        return self.labor_cost + self.parts_cost


class VehicleWarranty(Base):
    __tablename__ = "vehicle_warranties"
    __table_args__ = (
        Index(
            "ix_vehicle_warranties_dealership_end_date",
            "dealership_id",
            "end_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(150))
    policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    coverage: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    mileage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
