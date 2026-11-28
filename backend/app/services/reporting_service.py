from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.channel import Conversation
from app.models.user import User
from app.models.workspace import (
    CustomerLead,
    LeadActivity,
    NotificationDelivery,
    OutboxEvent,
    TestDriveBooking,
    Vehicle,
)


def get_dealership_report_summary(db: Session, dealership_id: int) -> dict[str, Any]:
    """
    Aggregates inventory, CRM lead funnel, test-drive, conversation,
    notification, and outbox observability metrics for a dealership.
    """
    vehicle_rows = db.execute(
        select(Vehicle.status, func.count(Vehicle.id), func.coalesce(func.sum(Vehicle.price), 0))
        .where(Vehicle.dealership_id == dealership_id)
        .group_by(Vehicle.status)
    ).all()
    inventory_by_status = {row[0] or "available": int(row[1]) for row in vehicle_rows}
    total_inventory_value = sum(float(row[2] or 0) for row in vehicle_rows)

    lead_rows = db.execute(
        select(
            CustomerLead.status,
            func.count(CustomerLead.id),
            func.coalesce(
                func.sum(
                    func.coalesce(
                        CustomerLead.deal_value,
                        CustomerLead.budget,
                        0,
                    )
                ),
                0,
            ),
        )
        .where(CustomerLead.dealership_id == dealership_id)
        .group_by(CustomerLead.status)
    ).all()
    leads_by_status = {row[0]: int(row[1]) for row in lead_rows}
    deal_value_by_status = {row[0]: float(row[2] or 0) for row in lead_rows}
    lead_source_rows = db.execute(
        select(CustomerLead.source, func.count(CustomerLead.id))
        .where(CustomerLead.dealership_id == dealership_id)
        .group_by(CustomerLead.source)
    ).all()
    leads_by_source = {
        source or "website": int(count) for source, count in lead_source_rows
    }
    won_deal_value = float(
        db.scalar(
            select(func.coalesce(func.sum(CustomerLead.deal_value), 0)).where(
                CustomerLead.dealership_id == dealership_id,
                CustomerLead.status == "won",
            )
        )
        or 0
    )

    booking_rows = db.execute(
        select(TestDriveBooking.status, func.count(TestDriveBooking.id))
        .where(TestDriveBooking.dealership_id == dealership_id)
        .group_by(TestDriveBooking.status)
    ).all()
    bookings_by_status = {row[0]: int(row[1]) for row in booking_rows}

    conv_rows = db.execute(
        select(Conversation.channel, func.count(Conversation.id))
        .where(Conversation.dealership_id == dealership_id)
        .group_by(Conversation.channel)
    ).all()
    conversations_by_channel = {row[0]: int(row[1]) for row in conv_rows}
    handoff_queue_count = int(
        db.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.dealership_id == dealership_id,
                Conversation.status == "handed_off",
            )
        )
        or 0
    )

    outbox_rows = db.execute(
        select(OutboxEvent.status, func.count(OutboxEvent.id))
        .where(OutboxEvent.dealership_id == dealership_id)
        .group_by(OutboxEvent.status)
    ).all()
    outbox_by_status = {row[0]: int(row[1]) for row in outbox_rows}

    notif_rows = db.execute(
        select(NotificationDelivery.status, func.count(NotificationDelivery.id))
        .where(NotificationDelivery.dealership_id == dealership_id)
        .group_by(NotificationDelivery.status)
    ).all()
    notifications_by_status = {row[0]: int(row[1]) for row in notif_rows}

    return {
        "dealership_id": dealership_id,
        "inventory": {
            "total": sum(inventory_by_status.values()),
            "by_status": inventory_by_status,
            "total_value": total_inventory_value,
        },
        "leads": {
            "total": sum(leads_by_status.values()),
            "by_status": leads_by_status,
            "deal_value_by_status": deal_value_by_status,
            "by_source": leads_by_source,
            "won_deal_value": won_deal_value,
        },
        "test_drives": {
            "total": sum(bookings_by_status.values()),
            "by_status": bookings_by_status,
        },
        "conversations": {
            "total": sum(conversations_by_channel.values()),
            "by_channel": conversations_by_channel,
            "handoff_queue": handoff_queue_count,
        },
        "observability": {
            "outbox_by_status": outbox_by_status,
            "notifications_by_status": notifications_by_status,
        },
    }


def get_dealership_report_analytics(
    db: Session,
    dealership_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    lead_scope = (
        CustomerLead.dealership_id == dealership_id,
        CustomerLead.created_at >= start,
        CustomerLead.created_at < end,
    )
    won_count = func.count(CustomerLead.id).filter(CustomerLead.status == "won")
    lead_rows = db.execute(
        select(CustomerLead.status, func.count(CustomerLead.id))
        .where(*lead_scope)
        .group_by(CustomerLead.status)
    ).all()
    by_status = {status: int(count) for status, count in lead_rows}

    source_rows = db.execute(
        select(
            CustomerLead.source,
            func.count(CustomerLead.id),
            won_count,
            func.coalesce(
                func.sum(CustomerLead.deal_value).filter(CustomerLead.status == "won"),
                0,
            ),
        )
        .where(*lead_scope)
        .group_by(CustomerLead.source)
        .order_by(func.count(CustomerLead.id).desc())
    ).all()
    by_source = [
        {
            "source": source,
            "leads": int(total),
            "won": int(won),
            "conversion_rate": round((int(won) / int(total)) * 100, 1),
            "won_deal_value": float(deal_value or 0),
        }
        for source, total, won, deal_value in source_rows
    ]

    rep_rows = db.execute(
        select(
            User.id,
            User.name,
            func.count(CustomerLead.id),
            won_count,
            func.coalesce(
                func.sum(CustomerLead.deal_value).filter(CustomerLead.status == "won"),
                0,
            ),
        )
        .select_from(CustomerLead)
        .outerjoin(User, User.id == CustomerLead.assigned_to_user_id)
        .where(*lead_scope)
        .group_by(User.id, User.name)
        .order_by(won_count.desc(), func.count(CustomerLead.id).desc())
    ).all()
    by_rep = [
        {
            "user_id": user_id,
            "name": name or "Unassigned",
            "leads": int(total),
            "won": int(won),
            "conversion_rate": round((int(won) / int(total)) * 100, 1),
            "won_deal_value": float(deal_value or 0),
        }
        for user_id, name, total, won, deal_value in rep_rows
    ]

    total_leads = sum(by_status.values())
    total_won = by_status.get("won", 0)
    activity_rows = db.execute(
        select(
            LeadActivity.activity_type,
            LeadActivity.created_at,
            LeadActivity.details,
        ).where(
            LeadActivity.dealership_id == dealership_id,
            LeadActivity.created_at >= start,
            LeadActivity.created_at < end,
            LeadActivity.activity_type.in_(("created", "status_changed")),
        )
    ).all()
    daily_metrics: dict[str, dict[str, int]] = {}
    stage_transitions: dict[str, int] = {}
    lost_reasons: dict[str, int] = {}
    close_rep_totals: dict[int | None, dict[str, int | float]] = {}
    for activity_type, created_at, details in activity_rows:
        day = created_at.date().isoformat()
        counts = daily_metrics.setdefault(
            day,
            {"leads_created": 0, "won": 0, "lost": 0},
        )
        if activity_type == "created":
            counts["leads_created"] += 1
            continue
        new_status = (details or {}).get("new_status")
        if new_status:
            stage_transitions[new_status] = stage_transitions.get(new_status, 0) + 1
            if new_status in {"won", "lost"}:
                counts[new_status] += 1
            if new_status == "lost":
                reason = (details or {}).get("lost_reason") or "unspecified"
                lost_reasons[reason] = lost_reasons.get(reason, 0) + 1
            if new_status == "won":
                assigned_user_id = (details or {}).get("assigned_to_user_id")
                if not isinstance(assigned_user_id, int):
                    assigned_user_id = None
                rep_totals = close_rep_totals.setdefault(
                    assigned_user_id,
                    {"won": 0, "won_deal_value": 0.0},
                )
                rep_totals["won"] += 1
                rep_totals["won_deal_value"] += float(
                    (details or {}).get("deal_value") or 0
                )

    close_rep_user_ids = [
        user_id for user_id in close_rep_totals if user_id is not None
    ]
    close_rep_names = (
        {
            user_id: name
            for user_id, name in db.execute(
                select(User.id, User.name).where(User.id.in_(close_rep_user_ids))
            ).all()
        }
        if close_rep_user_ids
        else {}
    )
    wins_by_rep_at_close = [
        {
            "user_id": user_id,
            "name": close_rep_names.get(
                user_id,
                "Unassigned / no historical attribution"
                if user_id is None
                else "Former team member",
            ),
            **totals,
        }
        for user_id, totals in sorted(
            close_rep_totals.items(),
            key=lambda item: (-item[1]["won"], str(item[0])),
        )
    ]

    booking_total = int(
        db.scalar(
            select(func.count(TestDriveBooking.id)).where(
                TestDriveBooking.dealership_id == dealership_id,
                TestDriveBooking.created_at >= start,
                TestDriveBooking.created_at < end,
            )
        )
        or 0
    )
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "leads": {
            "total": total_leads,
            "won": total_won,
            "conversion_rate": (
                round((total_won / total_leads) * 100, 1) if total_leads else 0
            ),
            "by_status": by_status,
        },
        "by_source": by_source,
        "by_rep": by_rep,
        "historical": {
            "daily": [
                {"date": day, **daily_metrics[day]}
                for day in sorted(daily_metrics)
            ],
            "stage_transitions": stage_transitions,
            "lost_by_reason": lost_reasons,
            "wins_by_rep_at_close": wins_by_rep_at_close,
        },
        "test_drives": {"total": booking_total},
    }
