#!/usr/bin/env python3
"""
CLI runner for DealerDesk data retention cleanup.
Can be executed manually or as a scheduled cron job.
Usage:
    python scripts/run_retention_cleanup.py [--dry-run] [--audit-days 365]
"""
import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.services.retention_service import cleanup_expired_data


def main() -> None:
    parser = argparse.ArgumentParser(description="DealerDesk Data Retention Cleaner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate cleanup without deleting rows",
    )
    parser.add_argument(
        "--audit-days",
        type=int,
        default=365,
        help="Number of days to keep audit logs (default: 365)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = cleanup_expired_data(
            db,
            dry_run=args.dry_run,
            audit_retention_days=args.audit_days,
        )
        mode = "DRY RUN" if report["dry_run"] else "EXECUTED"
        print(f"[{mode}] Cleanup summary at {report['executed_at']}:")
        for entity, count in report["cleaned_counts"].items():
            print(f"  - {entity}: {count} pruned")
        print(f"Total rows pruned: {report['total_pruned']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
