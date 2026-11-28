from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import worker
from app.services import gmail_service

pytestmark = pytest.mark.no_db


def test_worker_syncs_due_gmail_mailboxes_and_reschedules(monkeypatch) -> None:
    connection = SimpleNamespace(id=1, dealership_id=9)
    db = MagicMock()
    db.scalar.side_effect = [connection, None]
    monkeypatch.setattr(
        gmail_service,
        "sync_mailbox",
        lambda _db, dealership_id: {"threads": 2, "messages": 3},
    )

    stats = worker.sync_due_gmail_mailboxes(db)

    assert stats == {"evaluated": 1, "synced": 1, "failed": 0}
    assert db.scalar.call_count == 2


def test_worker_persists_retry_state_for_failed_gmail_sync(monkeypatch) -> None:
    connection = SimpleNamespace(
        id=1,
        dealership_id=9,
        sync_attempts=0,
        next_sync_at=None,
        last_sync_error=None,
    )
    db = MagicMock()
    db.scalar.side_effect = [connection, connection, None]

    def fail_sync(_db, _dealership_id):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(gmail_service, "sync_mailbox", fail_sync)

    stats = worker.sync_due_gmail_mailboxes(db)

    assert stats == {"evaluated": 1, "synced": 0, "failed": 1}
    assert connection.sync_attempts == 1
    assert connection.last_sync_error == "RuntimeError"
    assert connection.next_sync_at is not None
    db.commit.assert_called_once()
