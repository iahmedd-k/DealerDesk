from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GmailMailboxConnection(Base):
    __tablename__ = "gmail_mailbox_connections"
    __table_args__ = (
        UniqueConstraint("dealership_id", name="uq_gmail_mailbox_dealership"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dealership_id: Mapped[int] = mapped_column(
        ForeignKey("dealerships.id", ondelete="CASCADE"), index=True
    )
    gmail_address: Mapped[str] = mapped_column(String(320))
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    history_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    connected_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sync_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
