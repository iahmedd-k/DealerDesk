from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.workspace import CustomerLead, LeadActivity
from app.services.reporting_service import (
    get_dealership_report_analytics,
    get_dealership_report_summary,
)


def test_report_summary_aggregates_all_leads_by_status_and_source(db, seeded_users) -> None:
    _, admin, _ = seeded_users
    timestamp = datetime(2026, 3, 1, tzinfo=timezone.utc)
    db.add_all(
        [
            CustomerLead(
                dealership_id=admin.dealership_id,
                name="Website Lead",
                email="website@example.com",
                message="Looking for a sedan",
                source="website",
                status="new",
                budget=30000,
                created_at=timestamp,
                updated_at=timestamp,
            ),
            CustomerLead(
                dealership_id=admin.dealership_id,
                name="Referral Lead",
                email="referral@example.com",
                message="Looking for an SUV",
                source="referral",
                status="qualified",
                deal_value=42000,
                budget=40000,
                created_at=timestamp,
                updated_at=timestamp,
            ),
        ]
    )
    db.commit()

    report = get_dealership_report_summary(db, admin.dealership_id)

    assert report["leads"]["by_status"] == {"new": 1, "qualified": 1}
    assert report["leads"]["deal_value_by_status"] == {
        "new": 30000.0,
        "qualified": 42000.0,
    }
    assert report["leads"]["by_source"] == {"referral": 1, "website": 1}


def test_report_analytics_returns_empty_metrics_for_date_range(db: Session) -> None:
    report = get_dealership_report_analytics(
        db,
        dealership_id=987654,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    assert report["start_date"] == "2026-03-01"
    assert report["end_date"] == "2026-03-31"
    assert report["leads"] == {
        "total": 0,
        "won": 0,
        "conversion_rate": 0,
        "by_status": {},
    }
    assert report["by_source"] == []
    assert report["by_rep"] == []
    assert report["test_drives"]["total"] == 0


def test_report_analytics_counts_historical_stage_transitions(db, seeded_users) -> None:
    _, admin, _ = seeded_users
    lead = CustomerLead(
        dealership_id=admin.dealership_id,
        name="Historical Lead",
        email="historical-lead@example.com",
        message="Interested in a vehicle",
        source="referral",
        status="won",
        consent_to_contact=True,
        consented_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
    )
    db.add(lead)
    db.flush()
    lost_lead = CustomerLead(
        dealership_id=admin.dealership_id,
        name="Lost Lead",
        email="lost-lead@example.com",
        message="Could not agree on price",
        source="phone",
        status="lost",
        lost_reason="price",
        consent_to_contact=True,
        consented_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
    )
    db.add(lost_lead)
    db.flush()
    db.add_all(
        [
            LeadActivity(
                dealership_id=admin.dealership_id,
                lead_id=lead.id,
                activity_type="created",
                summary="Lead created",
                details={"source": "referral"},
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            LeadActivity(
                dealership_id=admin.dealership_id,
                lead_id=lead.id,
                activity_type="status_changed",
                summary="Lead won",
                details={
                    "previous_status": "qualified",
                    "new_status": "won",
                    "assigned_to_user_id": admin.id,
                    "deal_value": 32000,
                },
                created_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
            ),
            LeadActivity(
                dealership_id=admin.dealership_id,
                lead_id=lost_lead.id,
                activity_type="created",
                summary="Lead created",
                details={"source": "phone"},
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            LeadActivity(
                dealership_id=admin.dealership_id,
                lead_id=lost_lead.id,
                activity_type="status_changed",
                summary="Lead lost",
                details={
                    "previous_status": "qualified",
                    "new_status": "lost",
                    "lost_reason": "price",
                },
                created_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    report = get_dealership_report_analytics(
        db,
        dealership_id=admin.dealership_id,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    assert report["historical"] == {
        "daily": [
            {"date": "2026-03-01", "leads_created": 2, "won": 0, "lost": 0},
            {"date": "2026-03-03", "leads_created": 0, "won": 1, "lost": 0},
            {"date": "2026-03-04", "leads_created": 0, "won": 0, "lost": 1},
        ],
        "stage_transitions": {"won": 1, "lost": 1},
        "lost_by_reason": {"price": 1},
        "wins_by_rep_at_close": [
            {
                "user_id": admin.id,
                "name": admin.name,
                "won": 1,
                "won_deal_value": 32000.0,
            }
        ],
    }
