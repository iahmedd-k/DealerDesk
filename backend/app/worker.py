"""Periodic CRM jobs; run as a separate process with ``python -m app.worker``."""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.gmail import GmailMailboxConnection
from app.services import gmail_service, outbox_service, reminder_service

logger = logging.getLogger("dealerdesk.worker")
POLL_INTERVAL_SECONDS = 30
MAX_GMAIL_SYNCS_PER_RUN = 10


def sync_due_gmail_mailboxes(db: Session) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    stats = {"evaluated": 0, "synced": 0, "failed": 0}
    for _ in range(MAX_GMAIL_SYNCS_PER_RUN):
        connection = db.scalar(
            select(GmailMailboxConnection)
            .where(
                or_(
                    GmailMailboxConnection.next_sync_at.is_(None),
                    GmailMailboxConnection.next_sync_at <= now,
                )
            )
            .order_by(
                GmailMailboxConnection.next_sync_at.asc().nullsfirst(),
                GmailMailboxConnection.id.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if connection is None:
            break
        stats["evaluated"] += 1
        try:
            result = gmail_service.sync_mailbox(db, connection.dealership_id)
            stats["synced"] += 1
            logger.info(
                "Shared Gmail mailbox synced",
                extra={
                    "dealership_id": connection.dealership_id,
                    "threads": result["threads"],
                    "messages": result["messages"],
                },
            )
        except Exception as exc:
            dealership_id = connection.dealership_id
            connection_id = connection.id
            db.rollback()
            connection = db.scalar(
                select(GmailMailboxConnection)
                .where(GmailMailboxConnection.id == connection_id)
                .with_for_update(skip_locked=True)
            )
            if connection is not None:
                connection.sync_attempts += 1
                retry_minutes = min(60, 2 ** min(connection.sync_attempts, 6))
                connection.next_sync_at = now + timedelta(minutes=retry_minutes)
                connection.last_sync_error = type(exc).__name__[:128]
                db.commit()
            stats["failed"] += 1
            logger.warning(
                "Shared Gmail mailbox sync failed for dealership %s (%s)",
                dealership_id,
                type(exc).__name__,
            )
    return stats


def run_once() -> None:
    with SessionLocal() as db:
        reminders = reminder_service.process_due_booking_reminders(db)
        outbox = outbox_service.dispatch_pending_outbox_events(db, max_batch=100)
        gmail = sync_due_gmail_mailboxes(db)
    logger.info(
        "Background CRM jobs completed",
        extra={"reminders": reminders, "outbox": outbox, "gmail": gmail},
    )


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("DealerDesk background worker started")
    while True:
        started_at = time.monotonic()
        try:
            run_once()
        except Exception:
            logger.exception("Background CRM job iteration failed")
        time.sleep(max(0, POLL_INTERVAL_SECONDS - (time.monotonic() - started_at)))


if __name__ == "__main__":
    run_forever()
