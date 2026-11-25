from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.channel import Conversation
from app.models.workspace import (
    CustomerLead,
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
        select(CustomerLead.status, func.count(CustomerLead.id))
        .where(CustomerLead.dealership_id == dealership_id)
        .group_by(CustomerLead.status)
    ).all()
    leads_by_status = {row[0]: int(row[1]) for row in lead_rows}
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
