from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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


class LeadQuote(Base):
    __tablename__ = "lead_quotes"
    __table_args__ = (
        UniqueConstraint("lead_id", "version", name="uq_lead_quotes_lead_version"),
        CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'declined', 'expired')",
            name="ck_lead_quotes_status",
        ),
        Index("ix_lead_quotes_dealership_lead", "dealership_id", "lead_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("customer_leads.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vehicle_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    trade_in_vehicle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    trade_in_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0")
    )
    down_payment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0")
    )
    amount_financed: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    apr_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    loan_term_months: Mapped[int] = mapped_column(Integer)
    estimated_monthly_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    disclaimer: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
