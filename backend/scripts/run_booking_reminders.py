"""
Standalone cron/scheduled script to dispatch 24h and 2h test-drive booking reminders.
Usage:
    python -m scripts.run_booking_reminders [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.reminder_service import process_due_booking_reminders


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DealerDesk test-drive booking reminders")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate due reminders without sending emails or writing ledger rows",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = process_due_booking_reminders(db, dry_run=args.dry_run)
        print(json.dumps(report, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
