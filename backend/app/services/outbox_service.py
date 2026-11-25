from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
from typing import Any
import urllib.error
import urllib.request

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.workspace import OutboxEvent

logger = logging.getLogger("dealerdesk.outbox")

MAX_OUTBOX_ATTEMPTS = 5


def enqueue_event(
    db: Session,
    *,
    dealership_id: int,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str | int,
    payload: dict[str, Any],
    target_webhook_url: str | None = None,
    commit: bool = True,
) -> OutboxEvent:
    """
    Records a transactional outbox event for asynchronous webhook delivery
    and workflow observability.
    """
    now = datetime.now(timezone.utc)
    event = OutboxEvent(
        dealership_id=dealership_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
        target_webhook_url=target_webhook_url,
        status="pending",
        attempts=0,
        next_retry_at=now,
        created_at=now,
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event


def _deliver_webhook(
    url: str,
    event: OutboxEvent,
    signing_secret: str | None = None,
) -> None:
    body = json.dumps(
        {
            "id": event.id,
            "dealership_id": event.dealership_id,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "payload": event.payload,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-DealerDesk-Event": event.event_type,
    }
    if signing_secret:
        sig = hmac.new(signing_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-DealerDesk-Signature"] = f"sha256={sig}"

    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Webhook returned HTTP {resp.status}")


def dispatch_pending_outbox_events(
    db: Session,
    *,
    dealership_id: int | None = None,
    default_webhook_url: str | None = None,
    signing_secret: str | None = None,
    max_batch: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Dispatches due pending outbox events with exponential backoff retry
    and dead-letter marking after MAX_OUTBOX_ATTEMPTS.
    """
    now = datetime.now(timezone.utc)
    query = select(OutboxEvent).where(
        OutboxEvent.status == "pending",
        or_(OutboxEvent.next_retry_at.is_(None), OutboxEvent.next_retry_at <= now),
    )
    if dealership_id is not None:
        query = query.where(OutboxEvent.dealership_id == dealership_id)

    events = list(
        db.scalars(query.order_by(OutboxEvent.created_at.asc()).limit(max_batch))
    )

    stats = {
        "dry_run": dry_run,
        "evaluated": len(events),
        "delivered": 0,
        "skipped_no_target": 0,
        "retried": 0,
        "failed": 0,
    }

    for event in events:
        target = event.target_webhook_url or default_webhook_url
        if not target:
            stats["skipped_no_target"] += 1
            continue

        if dry_run:
            stats["delivered"] += 1
            continue

        event.attempts += 1
        try:
            _deliver_webhook(target, event, signing_secret=signing_secret)
            event.status = "delivered"
            event.delivered_at = now
            event.last_error = None
            stats["delivered"] += 1
        except (OSError, urllib.error.HTTPError, RuntimeError) as exc:
            event.last_error = str(exc)
            if event.attempts >= MAX_OUTBOX_ATTEMPTS:
                event.status = "failed"
                stats["failed"] += 1
            else:
                backoff_minutes = 2 ** (event.attempts - 1)
                event.next_retry_at = now + timedelta(minutes=backoff_minutes)
                stats["retried"] += 1
            logger.warning(
                "Outbox event %s delivery attempt %d failed: %s",
                event.id,
                event.attempts,
                exc,
            )

    if not dry_run and events:
        db.commit()

    return {"executed_at": now.isoformat(), **stats}


def list_outbox_events(
    db: Session,
    dealership_id: int,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[OutboxEvent]:
    query = select(OutboxEvent).where(OutboxEvent.dealership_id == dealership_id)
    if status:
        query = query.where(OutboxEvent.status == status)
    return list(
        db.scalars(
            query.order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
