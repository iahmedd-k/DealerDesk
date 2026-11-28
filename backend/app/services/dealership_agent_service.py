import csv
import html
import io
import ipaddress
import json
import logging
import re
import socket
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus, urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.redis import redis_client
from app.core.roles import DEALERDESK_ADMIN_ROLE, STAFF_ROLES
from app.core.safety import sanitize_output
from app.models.user import User
from app.models.workspace import Brand, Dealership, Vehicle
from app.schemas.workspace import (
    BrandCreateRequest,
    BrandUpdateRequest,
    CustomerLeadCreateRequest,
    CustomerLeadUpdateRequest,
    LeadActivityCreateRequest,
    StaffInvitationRequest,
    TestDriveBookingOutcomeRequest,
    TestDriveRescheduleRequest,
    TestDriveSettingsRequest,
    TestDriveSlotCreateRequest,
    TestDriveSlotUpdateRequest,
    VehicleCreateRequest,
    VehicleStatusTransitionRequest,
    VehicleUpdateRequest,
)
from app.services import (
    brand_service,
    conversation_service,
    lead_service,
    outbox_service,
    reminder_service,
    reporting_service,
    staff_service,
    test_drive_service,
    vehicle_service,
)


def _is_staff(current_user: User | None) -> bool:
    return current_user is not None and (
        current_user.role == DEALERDESK_ADMIN_ROLE or current_user.role in STAFF_ROLES
    )


def _invalidate_dealership_caches(dealership_id: int) -> None:
    redis_client.delete(
        f"dealerdesk:public:vehicles:{dealership_id}",
        f"dealerdesk:staff:vehicles:{dealership_id}",
        f"dealerdesk:brands:{dealership_id}",
        f"dealerdesk:reports:summary:{dealership_id}",
    )


def _find_vehicle(
    db: Session,
    dealership_id: int,
    *,
    vehicle_id: int | None = None,
    stock_number: str | None = None,
    query: str | None = None,
) -> Vehicle | None:
    if vehicle_id is not None:
        return db.scalar(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.dealership_id == dealership_id,
            )
        )
    if stock_number:
        found = db.scalar(
            select(Vehicle).where(
                Vehicle.dealership_id == dealership_id,
                Vehicle.stock_number.ilike(stock_number.strip()),
            )
        )
        if found:
            return found
    if query:
        q = query.strip().lower()
        vehicles = db.scalars(
            select(Vehicle).where(Vehicle.dealership_id == dealership_id)
        ).all()
        for v in vehicles:
            full = f"{v.model_year} {v.make} {v.model} {v.variant or ''}".lower()
            if q in full or q in v.stock_number.lower():
                return v
    return None


def _resolve_or_create_brand(
    db: Session,
    dealership_id: int,
    current_user: User,
    brand_name: str,
) -> Brand:
    normalized = brand_name.strip()
    existing = db.scalar(
        select(Brand).where(
            Brand.dealership_id == dealership_id,
            Brand.name.ilike(normalized),
            Brand.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    return brand_service.create_brand(
        db,
        dealership_id,
        current_user,
        BrandCreateRequest(name=normalized),
    )


def _parse_kv_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            key = k.strip().lower().replace(" ", "_")
            val = v.strip()
            if key and val:
                fields[key] = val
    return fields


def _extract_json_records(text: str) -> list[dict[str, Any]] | None:
    stripped = text.strip()
    match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", stripped)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
        return parsed
    return None


def _extract_csv_records(text: str) -> list[dict[str, Any]] | None:
    lines = [
        ln
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("[Uploaded file:")
    ]
    if len(lines) < 2 or "," not in lines[0]:
        return None
    header = lines[0].lower()
    if not any(col in header for col in ("model", "price", "stock")):
        return None
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    rows = [
        {k.strip().lower().replace(" ", "_"): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        for row in reader
    ]
    return rows or None


def _extract_nl_vehicle(text: str, brands: list[Brand]) -> dict[str, Any]:
    kv = _parse_kv_fields(text)
    if kv and any(k in kv for k in ("model", "make", "brand", "price", "stock", "stock_number")):
        return {
            "make": kv.get("make") or kv.get("brand"),
            "model": kv.get("model"),
            "model_year": int(kv["year"]) if kv.get("year", "").isdigit() else (
                int(kv["model_year"]) if kv.get("model_year", "").isdigit() else datetime.now().year
            ),
            "variant": kv.get("variant") or kv.get("trim"),
            "price": float(re.sub(r"[^\d.]", "", kv["price"])) if kv.get("price") else None,
            "stock_number": kv.get("stock_number") or kv.get("stock") or kv.get("stock_#"),
            "description": kv.get("description") or kv.get("notes"),
            "test_drive_enabled": kv.get("test_drive", "true").lower() in ("true", "yes", "1", "enabled"),
            "vin": kv.get("vin"),
            "mileage": int(re.sub(r"\D", "", kv["mileage"])) if kv.get("mileage") else None,
            "transmission": kv.get("transmission"),
            "fuel_type": kv.get("fuel_type") or kv.get("fuel"),
        }

    year_match = re.search(r"\b(19\d{2}|20[0-3]\d)\b", text)
    model_year = int(year_match.group(1)) if year_match else datetime.now().year

    price_match = re.search(
        r"(?:price\s*(?:is|=|:|of)?\s*\$?\s*|\$\s*)(\d[\d,]*(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE,
    )
    price = float(price_match.group(1).replace(",", "")) if price_match else None

    stock_match = re.search(
        r"(?:stock(?:\s*(?:number|#|id))?\s*(?:is|=|:)?\s*#?)([A-Za-z0-9_-]{2,32})",
        text,
        re.IGNORECASE,
    )
    stock_number = stock_match.group(1) if stock_match else None

    make: str | None = None
    for b in brands:
        if re.search(rf"\b{re.escape(b.name)}\b", text, re.IGNORECASE):
            make = b.name
            break

    model: str | None = None
    variant: str | None = None
    if make:
        after_make = re.split(rf"\b{re.escape(make)}\b", text, maxsplit=1, flags=re.IGNORECASE)[1]
        after_make = re.split(r"[,;\n]|price|\$|stock", after_make, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        tokens = after_make.split()
        if tokens:
            model = tokens[0]
            if len(tokens) > 1:
                variant = " ".join(tokens[1:])
    else:
        after_year = re.search(
            r"\b(?:19\d{2}|20[0-3]\d)\s+([A-Za-z0-9-]+)\s+([A-Za-z0-9-]+)(?:\s+([A-Za-z0-9-]+))?",
            text,
        )
        if after_year:
            make = after_year.group(1)
            model = after_year.group(2)
            variant = after_year.group(3)

    td_enabled = "test drive" in text.lower() and "disable" not in text.lower()

    return {
        "make": make,
        "model": model,
        "model_year": model_year,
        "variant": variant,
        "price": price,
        "stock_number": stock_number,
        "test_drive_enabled": td_enabled,
    }


def _create_vehicles_from_records(
    db: Session,
    dealership: Dealership,
    current_user: User,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    created: list[str] = []
    errors: list[str] = []

    for idx, rec in enumerate(records, start=1):
        make = str(rec.get("make") or rec.get("brand") or "").strip()
        model = str(rec.get("model") or "").strip()
        stock = str(rec.get("stock_number") or rec.get("stock") or "").strip()
        raw_price = rec.get("price")
        raw_year = rec.get("model_year") or rec.get("year") or datetime.now().year

        if not make or not model or not stock or raw_price is None:
            errors.append(
                f"Item #{idx}: missing required fields (need brand/make, model, price, and stock number)."
            )
            continue

        try:
            brand = _resolve_or_create_brand(db, dealership.id, current_user, make)
            payload = VehicleCreateRequest(
                brand_id=brand.id,
                model=model,
                model_year=int(raw_year),
                variant=(str(rec["variant"]).strip() if rec.get("variant") else None),
                description=(str(rec["description"]).strip() if rec.get("description") else None),
                price=Decimal(str(raw_price).replace(",", "").replace("$", "")),
                stock_number=stock,
                vin=(str(rec["vin"]).strip() if rec.get("vin") else None),
                mileage=(int(rec["mileage"]) if rec.get("mileage") not in (None, "") else None),
                transmission=(str(rec["transmission"]).strip() if rec.get("transmission") else None),
                fuel_type=(str(rec["fuel_type"]).strip() if rec.get("fuel_type") else None),
            )
            vehicle = vehicle_service.create_vehicle(db, dealership.id, current_user, payload)
            if rec.get("test_drive_enabled") in (True, "true", "True", "yes", "1", 1):
                vehicle = vehicle_service.update_vehicle(
                    db,
                    dealership.id,
                    vehicle.id,
                    current_user,
                    VehicleUpdateRequest(test_drive_enabled=True),
                )
            created.append(
                f"**{vehicle.model_year} {vehicle.make} {vehicle.model}** (ID #{vehicle.id}, Stock `#{vehicle.stock_number}`, ${float(vehicle.price):,.2f})"
            )
        except ApplicationError as exc:
            errors.append(f"Item #{idx} ({make} {model}): {exc.detail}")
        except (ValueError, TypeError) as exc:
            errors.append(f"Item #{idx}: invalid value ({exc})")

    if created:
        _invalidate_dealership_caches(dealership.id)

    lines: list[str] = []
    if created:
        lines.append(f"Added **{len(created)}** vehicle(s) to **{dealership.name}** inventory:\n")
        lines.extend(f"- {item}" for item in created)
    if errors:
        if lines:
            lines.append("")
        lines.append("Could not process:")
        lines.extend(f"- {err}" for err in errors)

    return {
        "intent": "agent_action",
        "response": "\n".join(lines),
        "suggested_actions": ["Give me a dashboard summary", "Create a test-drive slot"],
    }


def _parse_slot_datetime(text: str, tz_name: str) -> tuple[datetime, datetime] | None:
    zone = ZoneInfo(tz_name or "UTC")
    now_local = datetime.now(zone)

    target_date: date | None = None
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if date_match:
        target_date = date.fromisoformat(date_match.group(1))
    elif "tomorrow" in text.lower():
        target_date = now_local.date() + timedelta(days=1)
    elif "today" in text.lower():
        target_date = now_local.date()
    else:
        target_date = now_local.date() + timedelta(days=1)

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.IGNORECASE)
    hour = 10
    minute = 0
    for m in re.finditer(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b|\b(\d{1,2})\s*(am|pm)\b", text, re.IGNORECASE):
        if m.group(1) is not None:
            hour = int(m.group(1))
            minute = int(m.group(2))
            ampm = (m.group(3) or "").lower()
        else:
            hour = int(m.group(4))
            minute = 0
            ampm = (m.group(5) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        break
    else:
        if time_match and time_match.group(3):
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)

    dur_match = re.search(r"(\d+)\s*(?:min|minute|minutes)", text, re.IGNORECASE)
    duration = int(dur_match.group(1)) if dur_match else 30

    starts_local = datetime.combine(target_date, time(hour=hour, minute=minute), tzinfo=zone)
    ends_local = starts_local + timedelta(minutes=duration)
    return starts_local.astimezone(timezone.utc), ends_local.astimezone(timezone.utc)


def _ok(response: str, suggested_actions: list[str] | None = None) -> dict[str, Any]:
    return {
        "intent": "agent_action",
        "response": response,
        "suggested_actions": suggested_actions or [],
    }


def try_execute_staff_action(
    db: Session,
    dealership: Dealership,
    current_user: User | None,
    message: str,
) -> dict[str, Any] | None:
    """
    Full Dealership CRM Operations Agent for authenticated dealership staff.
    Handles dashboard summaries, inventory/brand CRUD, test-drive slots/settings/bookings,
    leads & pipeline, inbox conversations, team invitations/availability, outbox & reminders.
    Returns None for normal read/RAG queries.
    """
    if not _is_staff(current_user) or current_user is None:
        return None

    text = message.strip()
    # Normalize common user typos in action commands while keeping original text for values
    normalized_cmd = re.sub(r"\ba+d+d+\b", "add", text.lower())
    normalized_cmd = re.sub(r"\bveh[a-z]{2,6}l[a-z]{0,2}s?\b", "vehicle", normalized_cmd)
    normalized_cmd = re.sub(r"\blsot\b", "slot", normalized_cmd)
    lower = normalized_cmd

    # 0. Help / Capabilities
    if re.search(r"\b(what can you do|help|agent commands|capabilities)\b", lower):
        return _ok(
            f"As **{dealership.name}**'s Operations Agent, I can execute any CRM dashboard action:\n\n"
            "- **Dashboard & Reports:** `Give me a dashboard summary`, `Show handoff queue`\n"
            "- **Inventory:** `Add vehicle 2026 Toyota Camry XSE, price $38500, stock #CAM-2026, test drive enabled`, upload CSV/JSON, `Update vehicle #3 price to $35000`, `Mark stock #CAM-2026 as sold`, `Delete vehicle #5`\n"
            "- **Brands:** `Add brand Lexus`, `Restore brand #2`, `Deactivate brand #2`\n"
            "- **Test Drives:** `Generate test-drive slots for the next 7 days`, `Create slot for vehicle #3 tomorrow at 11:00 capacity 2`, `Update slot #7 capacity to 4`, `Delete slot #7`, `Mark booking #2 as completed` / `no-show`, `Cancel booking #2`, `Reschedule booking #2 to slot #9`\n"
            "- **Leads & Pipeline:** `Create lead for Jane Doe, email jane@example.com, phone 555-0100, message Interested in Civic`, `Auto-assign lead #2`, `Update lead #2 status to qualified`, `Set lead #2 deal value to $38000`, `Add note to lead #2: Called customer`, `Convert lead #2 to booking #5`, `Delete lead #2`\n"
            "- **Inbox & Team:** `Reply to conversation #4: We will call you shortly`, `Handoff conversation #4`, `Close conversation #4`, `Assign conversation #4 to rep #2`, `Invite sales rep john@dealer.com name John Doe`, `Set my availability to unavailable`\n"
            "- **Operations:** `Dispatch outbox events`, `Run appointment reminders`"
        )

    # 1. Uploaded or pasted JSON / CSV vehicle batch
    json_records = _extract_json_records(text)
    if json_records is not None and any(
        "model" in r or "stock_number" in r or "stock" in r for r in json_records
    ):
        return _create_vehicles_from_records(db, dealership, current_user, json_records)

    csv_records = _extract_csv_records(text)
    if csv_records is not None:
        return _create_vehicles_from_records(db, dealership, current_user, csv_records)

    # 2. Dashboard / Operations Summary
    if re.search(r"\b(dashboard|operations|pipeline|crm)\s*(summary|stats|report|overview)\b", lower):
        summary = reporting_service.get_dealership_report_summary(db, dealership.id)
        inv = summary["inventory"]
        lds = summary["leads"]
        tds = summary["test_drives"]
        conv = summary["conversations"]
        return _ok(
            f"**{dealership.name} — Live CRM Summary**\n\n"
            f"- **Inventory:** {inv.get('total', 0)} total units "
            f"({inv.get('by_status', {}).get('available', 0)} available, "
            f"{inv.get('by_status', {}).get('sold', 0)} sold)\n"
            f"- **Leads:** {lds.get('total', 0)} total · Won deal value: "
            f"**${float(lds.get('won_deal_value', 0)):,.2f}**\n"
            f"- **Test Drives:** {tds.get('by_status', {}).get('booked', 0)} booked, "
            f"{tds.get('by_status', {}).get('completed', 0)} completed, "
            f"{tds.get('by_status', {}).get('no_show', 0)} no-show\n"
            f"- **Inbox:** {conv.get('total', 0)} conversations "
            f"(**{conv.get('handoff_queue', 0)}** in handoff queue)",
            ["Show handoff queue", "Generate test-drive slots for the next 7 days"],
        )

    # 3. Operations: Dispatch Outbox / Run Reminders
    if re.search(r"\bdispatch\b.*\boutbox\b", lower):
        try:
            res = outbox_service.dispatch_pending_outbox_events(db, dealership_id=dealership.id)
            return _ok(
                f"Dispatched outbox events for **{dealership.name}**: "
                f"**{res.get('delivered', 0)}** delivered, **{res.get('failed', 0)}** failed, "
                f"**{res.get('processed', 0)}** processed."
            )
        except ApplicationError as exc:
            return _ok(f"Could not dispatch outbox events: {exc.detail}")

    if re.search(r"\b(run|send|trigger)\b.*\breminders?\b", lower):
        try:
            res = reminder_service.process_due_booking_reminders(db, dealership_id=dealership.id)
            return _ok(
                f"Processed appointment reminders for **{dealership.name}**: "
                f"**{res.get('sent', 0)}** sent, **{res.get('skipped', 0)}** skipped, "
                f"**{res.get('failed', 0)}** failed."
            )
        except ApplicationError as exc:
            return _ok(f"Could not run reminders: {exc.detail}")

    # 4. Staff: Toggle Availability or Invite Staff
    if re.search(r"\b(my availability|set me|mark me)\b", lower) and any(
        w in lower for w in ("available", "unavailable")
    ):
        target_avail = "unavailable" not in lower
        try:
            updated_user = staff_service.update_staff(
                db,
                dealership.id,
                current_user.id,
                current_user,
                {"is_available": target_avail} if False else __import__("app.schemas.workspace", fromlist=["StaffUpdateRequest"]).StaffUpdateRequest(is_available=target_avail),
            )
            return _ok(
                f"Updated your lead-routing availability to **{'available' if updated_user.is_available else 'unavailable'}**."
            )
        except ApplicationError as exc:
            return _ok(f"Could not update availability: {exc.detail}")

    if re.search(r"\binvite\b", lower):
        email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        if not email_match:
            return _ok("Please include the staff member's email address (e.g., `Invite sales rep john@dealer.com name John Doe`).")
        inv_email = email_match.group(0)
        role = "manager" if "manager" in lower else "sales_rep"
        name_match = re.search(r"name\s+([A-Za-z][A-Za-z\s'-]{1,60})", text, re.IGNORECASE)
        inv_name = name_match.group(1).strip() if name_match else inv_email.split("@")[0].replace(".", " ").title()
        try:
            inv = staff_service.invite_staff(
                db,
                dealership.id,
                current_user,
                StaffInvitationRequest(name=inv_name, email=inv_email, role=role),
            )
            return _ok(f"Sent **{inv.role}** invitation to **{inv.name}** (`{inv.email}`).")
        except ApplicationError as exc:
            return _ok(f"Could not invite staff: {exc.detail}")

    # 5. Inbox / Conversations
    if re.search(r"\b(show|list)\b.*\bhandoff", lower):
        convs = conversation_service.list_conversations(
            db, dealership.id, status="handed_off", page=1, page_size=10
        )
        if not convs:
            return _ok("No conversations are currently waiting in the handoff queue.")
        lines = [f"- **Conv #{c.id}** ({c.channel} · `{c.channel_user_id}`): {getattr(c, 'handoff_reason', None) or 'Callback requested'}" for c in convs]
        return _ok(f"**Handoff Queue ({len(convs)}):**\n\n" + "\n".join(lines))

    conv_match = re.search(r"\b(?:conversation|conv|thread)\s*#?(\d+)\b", lower)
    if conv_match:
        conv_id = int(conv_match.group(1))
        try:
            if re.search(r"\b(reply|send|message)\b", lower) and ":" in text:
                reply_body = text.split(":", 1)[1].strip()
                if not reply_body:
                    return _ok(f"Include the reply text after `:` (e.g., `Reply to conversation #{conv_id}: We will call you shortly`).")
                conversation_service.add_staff_reply(db, dealership.id, conv_id, current_user, reply_body)
                return _ok(f"Sent staff reply to **Conversation #{conv_id}**.")

            assign_rep = re.search(r"\brep\s*#?(\d+)\b", lower)
            next_status = (
                "closed"
                if "close" in lower
                else "handed_off"
                if "handoff" in lower
                else "active"
                if any(w in lower for w in ("resume", "active", "reopen"))
                else None
            )
            if next_status is None and assign_rep is None:
                return _ok(f"Specify an action for **Conversation #{conv_id}** (`handoff`, `close`, `resume AI`, `assign to rep #2`, or `reply to conversation #{conv_id}: ...`).")
            existing_conv = conversation_service.get_conversation_for_dealership(db, dealership.id, conv_id)
            target_status = next_status or existing_conv.status
            updated_conv = conversation_service.update_conversation_status(
                db,
                dealership.id,
                conv_id,
                status=target_status,
                staff_user=current_user,
                assigned_to_user_id=int(assign_rep.group(1)) if assign_rep else None,
                assignment_provided=assign_rep is not None,
            )
            return _ok(
                f"Updated **Conversation #{updated_conv.id}** — status: **{updated_conv.status}**"
                + (f", assigned to rep **#{updated_conv.assigned_to_user_id}**" if updated_conv.assigned_to_user_id else "")
                + "."
            )
        except ApplicationError as exc:
            return _ok(f"Could not update Conversation #{conv_id}: {exc.detail}")

    # 6. Test-Drive Settings
    if re.search(r"\b(update|set|change)\b.*\btest[\s-]?drive\s+settings\b", lower):
        open_m = re.search(r"opening\s*(\d{2}:\d{2})", lower)
        close_m = re.search(r"closing\s*(\d{2}:\d{2})", lower)
        dur_m = re.search(r"duration\s*(\d+)", lower)
        cap_m = re.search(r"capacity\s*(\d+)", lower)
        try:
            current_s = test_drive_service.get_settings(db, dealership.id)
            updated_s = test_drive_service.upsert_settings(
                db,
                dealership.id,
                current_user,
                TestDriveSettingsRequest(
                    opening_time=open_m.group(1) if open_m else current_s.opening_time,
                    closing_time=close_m.group(1) if close_m else current_s.closing_time,
                    slot_duration_minutes=int(dur_m.group(1)) if dur_m else current_s.slot_duration_minutes,
                    capacity_per_slot=int(cap_m.group(1)) if cap_m else current_s.capacity_per_slot,
                    days_open=current_s.days_open,
                ),
            )
            return _ok(
                f"Updated test-drive settings: **{updated_s.opening_time}–{updated_s.closing_time}**, "
                f"**{updated_s.slot_duration_minutes} min** slots, capacity **{updated_s.capacity_per_slot}**."
            )
        except ApplicationError as exc:
            return _ok(f"Could not update test-drive settings: {exc.detail}")

    # 7. Generate test-drive slots from dealership schedule
    if re.search(r"\bgenerate\b.*\bslots?\b", lower):
        days_match = re.search(r"(\d+)\s*days?", lower)
        days = max(1, min(30, int(days_match.group(1)))) if days_match else 7
        start = datetime.now(ZoneInfo(dealership.timezone or "UTC")).date()
        end = start + timedelta(days=days)
        try:
            slots = test_drive_service.generate_slots(
                db, dealership.id, current_user, start_date=start, end_date=end
            )
            return _ok(
                f"Generated **{len(slots)}** test-drive slot(s) from **{start.isoformat()}** "
                f"to **{end.isoformat()}** using dealership schedule settings.",
                ["View test-drive slots", "Give me a dashboard summary"],
            )
        except ApplicationError as exc:
            return _ok(f"Could not generate slots: {exc.detail}")

    # 8. Delete / Update an existing test-drive slot
    slot_match = re.search(r"\bslot\s*#?(\d+)\b", lower)
    if slot_match and any(w in lower for w in ("delete", "remove")):
        slot_id = int(slot_match.group(1))
        try:
            test_drive_service.delete_slot(db, dealership.id, slot_id, current_user)
            return _ok(f"Deleted **Slot #{slot_id}**.")
        except ApplicationError as exc:
            return _ok(f"Could not delete Slot #{slot_id}: {exc.detail}")

    if slot_match and any(w in lower for w in ("update", "change", "set", "capacity", "disable", "enable", "deactivate", "activate")):
        slot_id = int(slot_match.group(1))
        cap_match = re.search(r"capacity\s*(?:to|=|:)?\s*(\d+)", lower)
        is_active: bool | None = None
        if any(w in lower for w in ("disable", "deactivate", "inactive")):
            is_active = False
        elif any(w in lower for w in ("enable", "activate")):
            is_active = True

        capacity = int(cap_match.group(1)) if cap_match else None
        if capacity is None and is_active is None:
            return _ok(f"Specify what to update on **Slot #{slot_id}** (e.g. `capacity to 3`, `disable`, or `enable`).")
        try:
            updated = test_drive_service.update_slot(
                db,
                dealership.id,
                slot_id,
                current_user,
                TestDriveSlotUpdateRequest(capacity=capacity, is_active=is_active),
            )
            return _ok(
                f"Updated **Slot #{updated.id}** — capacity: **{updated.capacity}**, "
                f"status: **{'active' if updated.is_active else 'disabled'}**."
            )
        except ApplicationError as exc:
            return _ok(f"Could not update Slot #{slot_id}: {exc.detail}")

    # 9. Create a new test-drive slot
    if re.search(r"\b(create|add|schedule|open)\b.*\bslot\b", lower):
        veh_id_match = re.search(r"vehicle\s*#?(\d+)", lower)
        stock_match = re.search(r"stock\s*#?([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        vehicle = _find_vehicle(
            db,
            dealership.id,
            vehicle_id=int(veh_id_match.group(1)) if veh_id_match else None,
            stock_number=stock_match.group(1) if stock_match else None,
        )
        if vehicle is None:
            return _ok("Specify which vehicle to create the slot for (e.g., `vehicle #3` or `stock #BOOK-001`).")
        cap_match = re.search(r"capacity\s*(?:to|=|:)?\s*(\d+)", lower)
        capacity = int(cap_match.group(1)) if cap_match else 1
        dt_pair = _parse_slot_datetime(text, dealership.timezone)
        if dt_pair is None:
            return _ok("Could not parse the requested slot date/time.")
        starts_at, ends_at = dt_pair
        try:
            slot = test_drive_service.create_slot(
                db,
                dealership.id,
                current_user,
                TestDriveSlotCreateRequest(
                    vehicle_id=vehicle.id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    capacity=capacity,
                ),
            )
            return _ok(
                f"Created **Slot #{slot.id}** for **{vehicle.model_year} {vehicle.make} {vehicle.model}** "
                f"at **{slot.starts_at.strftime('%Y-%m-%d %H:%M UTC')}** (capacity: **{slot.capacity}**)."
            )
        except ApplicationError as exc:
            return _ok(f"Could not create slot: {exc.detail}")

    # 10. Brands (Create / Restore / Activate / Deactivate)
    brand_id_match = re.search(r"\bbrand\s*#?(\d+)\b", lower)
    if brand_id_match:
        bid = int(brand_id_match.group(1))
        try:
            if "restore" in lower:
                b = brand_service.restore_brand(db, dealership.id, bid, current_user)
                _invalidate_dealership_caches(dealership.id)
                return _ok(f"Restored brand **{b.name}** (#{b.id}).")
            if any(w in lower for w in ("deactivate", "disable")):
                b = brand_service.update_brand(db, dealership.id, bid, current_user, BrandUpdateRequest(is_active=False))
                _invalidate_dealership_caches(dealership.id)
                return _ok(f"Deactivated brand **{b.name}** (#{b.id}).")
            if any(w in lower for w in ("activate", "enable")):
                b = brand_service.update_brand(db, dealership.id, bid, current_user, BrandUpdateRequest(is_active=True))
                _invalidate_dealership_caches(dealership.id)
                return _ok(f"Activated brand **{b.name}** (#{b.id}).")
        except ApplicationError as exc:
            return _ok(f"Could not update Brand #{bid}: {exc.detail}")

    add_brand_m = re.search(r"\b(?:add|create)\s+brand\s+([A-Za-z0-9\s&-]{2,40})", text, re.IGNORECASE)
    if add_brand_m:
        bname = add_brand_m.group(1).strip()
        try:
            b = brand_service.create_brand(db, dealership.id, current_user, BrandCreateRequest(name=bname))
            _invalidate_dealership_caches(dealership.id)
            return _ok(f"Added brand **{b.name}** (ID #{b.id}).")
        except ApplicationError as exc:
            return _ok(f"Could not add brand `{bname}`: {exc.detail}")

    # 11. Delete Vehicle
    if re.search(r"\b(delete|remove)\b.*\b(vehicle|car)\b", lower):
        veh_id_match = re.search(r"vehicle\s*#?(\d+)", lower)
        stock_match = re.search(r"stock\s*#?([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        vehicle = _find_vehicle(
            db,
            dealership.id,
            vehicle_id=int(veh_id_match.group(1)) if veh_id_match else None,
            stock_number=stock_match.group(1) if stock_match else None,
        )
        if vehicle is None:
            return _ok("Specify the vehicle to delete by ID or stock number (e.g., `Delete vehicle #5` or `Delete vehicle stock #AGT-999`).")
        try:
            vehicle_service.delete_vehicle(db, dealership.id, vehicle.id, current_user)
            _invalidate_dealership_caches(dealership.id)
            return _ok(f"Deleted **{vehicle.model_year} {vehicle.make} {vehicle.model}** (ID #{vehicle.id}, Stock `#{vehicle.stock_number}`).")
        except ApplicationError as exc:
            return _ok(f"Could not delete vehicle: {exc.detail}")

    # 12. Add / Create a vehicle from natural language or pasted key-value text
    if re.search(r"\b(add|create|upload|insert|register)\b.*\b(vehicle|vehicles|car|cars)\b", lower) or (
        "stock" in lower and "price" in lower and ("make:" in lower or "model:" in lower)
    ):
        brands = db.scalars(
            select(Brand).where(Brand.dealership_id == dealership.id, Brand.is_deleted.is_(False))
        ).all()
        rec = _extract_nl_vehicle(text, list(brands))
        if not rec.get("make") or not rec.get("model") or not rec.get("stock_number") or rec.get("price") is None:
            return _ok(
                "Yes, I can add a vehicle to your inventory! Please provide the **Year, Make, Model, Price, and Stock #** — "
                "or click the **paperclip (📎)** button to upload a `.csv` or `.json` file.\n\n"
                "**Example:** `Add vehicle 2026 Toyota Camry XSE, price $38500, stock #CAM-2026, test drive enabled`",
                ["Add vehicle 2026 Toyota Camry XSE, price $38500, stock #CAM-2026, test drive enabled"],
            )
        return _create_vehicles_from_records(db, dealership, current_user, [rec])

    # 13. Update an existing vehicle (price, status, test drive)
    if re.search(r"\b(update|mark|set|change|enable|disable)\b.*\b(vehicle|car|stock)\b", lower):
        veh_id_match = re.search(r"vehicle\s*#?(\d+)", lower)
        stock_match = re.search(r"stock\s*#?([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        vehicle = _find_vehicle(
            db,
            dealership.id,
            vehicle_id=int(veh_id_match.group(1)) if veh_id_match else None,
            stock_number=stock_match.group(1) if stock_match else None,
        )
        if vehicle is None:
            return _ok("Specify the vehicle by ID or stock number (e.g., `vehicle #3` or `stock #DEMO-001`).")
        try:
            actions_done: list[str] = []
            price_match = re.search(r"(?:price\s*(?:to|=|:)?\s*\$?\s*|\$\s*)(\d[\d,]*(?:\.\d{1,2})?)", text, re.IGNORECASE)
            td_change: bool | None = None
            if "enable test drive" in lower:
                td_change = True
            elif "disable test drive" in lower:
                td_change = False

            if price_match or td_change is not None:
                vehicle = vehicle_service.update_vehicle(
                    db,
                    dealership.id,
                    vehicle.id,
                    current_user,
                    VehicleUpdateRequest(
                        price=Decimal(price_match.group(1).replace(",", "")) if price_match else None,
                        test_drive_enabled=td_change,
                    ),
                )
                if price_match:
                    actions_done.append(f"price updated to **${float(vehicle.price):,.2f}**")
                if td_change is not None:
                    actions_done.append(f"test drive **{'enabled' if td_change else 'disabled'}**")

            status_match = re.search(r"\b(available|reserved|sold|in_transit|unavailable)\b", lower)
            if status_match:
                new_status = status_match.group(1)
                vehicle = vehicle_service.transition_vehicle_status(
                    db,
                    dealership.id,
                    vehicle.id,
                    current_user,
                    VehicleStatusTransitionRequest(status=new_status, notes="Updated via Dealership Agent"),
                )
                actions_done.append(f"status set to **{vehicle.status}**")

            if not actions_done:
                return _ok(f"Specify what to update on **{vehicle.make} {vehicle.model}** (price, status like `sold`/`available`, or `enable test drive`).")

            _invalidate_dealership_caches(dealership.id)
            return _ok(f"Updated **{vehicle.model_year} {vehicle.make} {vehicle.model}** (`#{vehicle.stock_number}`): " + ", ".join(actions_done) + ".")
        except ApplicationError as exc:
            return _ok(f"Could not update vehicle: {exc.detail}")

    # 14. Bookings (Completed, No-Show, Cancel, Reschedule)
    booking_match = re.search(r"\bbooking\s*#?(\d+)\b", lower)
    if booking_match:
        booking_id = int(booking_match.group(1))
        try:
            if any(w in lower for w in ("no-show", "no show", "no_show", "completed", "complete")):
                outcome = "no_show" if any(w in lower for w in ("no-show", "no show", "no_show")) else "completed"
                updated = test_drive_service.update_booking_outcome(
                    db, dealership.id, booking_id, current_user, TestDriveBookingOutcomeRequest(status=outcome)
                )
                return _ok(f"Marked **Booking #{updated.id}** as **{updated.status.replace('_', ' ')}**.")
            if "cancel" in lower:
                test_drive_service.cancel_booking(db, dealership.id, booking_id, current_user)
                return _ok(f"Cancelled **Booking #{booking_id}**.")
            if "reschedule" in lower:
                target_slot = re.search(r"slot\s*#?(\d+)", lower)
                if not target_slot:
                    return _ok(f"Specify the target slot to reschedule **Booking #{booking_id}** (e.g., `Reschedule booking #{booking_id} to slot #9`).")
                updated = test_drive_service.reschedule_booking(
                    db,
                    dealership.id,
                    booking_id,
                    TestDriveRescheduleRequest(new_slot_id=int(target_slot.group(1))),
                    current_user,
                )
                return _ok(f"Rescheduled **Booking #{updated.id}** to **Slot #{updated.slot_id}**.")
        except ApplicationError as exc:
            return _ok(f"Could not update Booking #{booking_id}: {exc.detail}")

    # 15. Leads (Create, Delete, Add Note, Convert, Auto-Assign, Update Stage/Deal Value)
    if re.search(r"\b(create|add)\s+lead\b", lower):
        email_m = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        if not email_m:
            return _ok("Include the customer's email to create a lead (e.g., `Create lead for Jane Doe, email jane@example.com, message Interested in Civic`).")
        l_email = email_m.group(0)
        name_m = re.search(r"(?:for|name)\s+([A-Za-z][A-Za-z\s'-]{1,60})(?:,|\bemail\b|\bphone\b|\bmessage\b|$)", text, re.IGNORECASE)
        l_name = name_m.group(1).strip() if name_m else l_email.split("@")[0].title()
        phone_m = re.search(r"phone\s*[:=]?\s*([+\d][\d\s()-]{5,24})", text, re.IGNORECASE)
        msg_m = re.search(r"message\s*[:=]?\s*(.+)$", text, re.IGNORECASE)
        l_msg = msg_m.group(1).strip() if msg_m else "Created via Dealership Operations Agent"
        try:
            lead = lead_service.create_lead(
                db,
                dealership.id,
                CustomerLeadCreateRequest(
                    name=l_name,
                    email=l_email,
                    phone=phone_m.group(1).strip() if phone_m else None,
                    message=l_msg,
                    source="phone",
                    consent_to_contact=True,
                ),
                current_user,
            )
            _invalidate_dealership_caches(dealership.id)
            return _ok(f"Created **Lead #{lead.id}** for **{lead.name}** (`{lead.email}`).")
        except ApplicationError as exc:
            return _ok(f"Could not create lead: {exc.detail}")

    lead_match = re.search(r"\blead\s*#?(\d+)\b", lower)
    if lead_match:
        lead_id = int(lead_match.group(1))
        try:
            if any(w in lower for w in ("delete", "remove")):
                lead_service.delete_lead(db, dealership.id, lead_id, current_user)
                _invalidate_dealership_caches(dealership.id)
                return _ok(f"Deleted **Lead #{lead_id}**.")
            if "note" in lower and ":" in text:
                note_body = text.split(":", 1)[1].strip()
                lead_service.add_lead_activity(
                    db, dealership.id, lead_id, current_user, LeadActivityCreateRequest(activity_type="note", summary=note_body)
                )
                return _ok(f"Added activity note to **Lead #{lead_id}**.")
            if "convert" in lower:
                b_m = re.search(r"booking\s*#?(\d+)", lower)
                if not b_m:
                    return _ok(f"Specify the booking ID to link (e.g., `Convert lead #{lead_id} to booking #5`).")
                lead = lead_service.convert_lead_to_booking(db, dealership.id, lead_id, int(b_m.group(1)), current_user)
                _invalidate_dealership_caches(dealership.id)
                return _ok(f"Linked **Lead #{lead.id}** to **Booking #{b_m.group(1)}**.")
            if "auto" in lower and "assign" in lower:
                lead = lead_service.auto_assign_lead(db, dealership.id, lead_id, current_user)
                return _ok(f"Auto-assigned **Lead #{lead.id}** ({lead.name}) to rep **#{lead.assigned_to_user_id}**.")
            stage_match = re.search(r"\b(new|contacted|qualified|follow_up|won|lost)\b", lower)
            val_match = re.search(r"(?:deal\s*value|value|price)\s*(?:to|=|:)?\s*\$?\s*(\d[\d,]*(?:\.\d{1,2})?)", lower)
            if stage_match or val_match:
                lead = lead_service.update_lead(
                    db,
                    dealership.id,
                    lead_id,
                    current_user,
                    CustomerLeadUpdateRequest(
                        status=stage_match.group(1) if stage_match else None,
                        deal_value=Decimal(val_match.group(1).replace(",", "")) if val_match else None,
                    ),
                )
                _invalidate_dealership_caches(dealership.id)
                return _ok(
                    f"Updated **Lead #{lead.id}** ({lead.name}) — stage: **{lead.status}**"
                    + (f", deal value: **${float(lead.deal_value):,.2f}**" if lead.deal_value is not None else "")
                    + "."
                )
        except ApplicationError as exc:
            return _ok(f"Could not update Lead #{lead_id}: {exc.detail}")

    return None


logger = logging.getLogger("dealerdesk.agent")

_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": "Get live CRM summary metrics (inventory counts, leads, won value, test drives, inbox handoffs).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_vehicles",
            "description": "List vehicles in this dealership's inventory.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_vehicle",
            "description": "Create a new vehicle in dealership inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "make": {"type": "string", "description": "Brand/make name, e.g. Toyota"},
                    "model": {"type": "string", "description": "Model name, e.g. Camry"},
                    "model_year": {"type": "integer", "description": "4-digit model year"},
                    "price": {"type": "number", "description": "Price in USD"},
                    "stock_number": {"type": "string", "description": "Unique stock number"},
                    "variant": {"type": "string"},
                    "description": {"type": "string"},
                    "test_drive_enabled": {"type": "boolean"},
                },
                "required": ["make", "model", "model_year", "price", "stock_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_vehicle",
            "description": "Update an existing vehicle's price, test_drive_enabled, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_id": {"type": "integer"},
                    "stock_number": {"type": "string"},
                    "price": {"type": "number"},
                    "status": {"type": "string", "enum": ["available", "reserved", "sold", "in_transit", "unavailable"]},
                    "test_drive_enabled": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_vehicle",
            "description": "Delete a vehicle by ID or stock_number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_id": {"type": "integer"},
                    "stock_number": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_brand",
            "description": "Create a new brand in the dealership.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_slots",
            "description": "List test-drive slots.",
            "parameters": {
                "type": "object",
                "properties": {"vehicle_id": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_slot",
            "description": "Create a single test-drive slot for a vehicle.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_id": {"type": "integer"},
                    "starts_at_iso": {"type": "string", "description": "ISO-8601 UTC timestamp, e.g. 2026-11-28T10:00:00Z"},
                    "duration_minutes": {"type": "integer", "default": 30},
                    "capacity": {"type": "integer", "default": 1},
                },
                "required": ["vehicle_id", "starts_at_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_slots",
            "description": "Generate test-drive slots for the next N days from dealership schedule settings.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "default": 7}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_slot",
            "description": "Update an existing test-drive slot's capacity or is_active flag.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "integer"},
                    "capacity": {"type": "integer"},
                    "is_active": {"type": "boolean"},
                },
                "required": ["slot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_booking_outcome",
            "description": "Mark a test-drive booking as completed or no_show.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["completed", "no_show"]},
                    "outcome_notes": {"type": "string"},
                },
                "required": ["booking_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_leads",
            "description": "List recent CRM leads.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Create a new customer lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["name", "email", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead",
            "description": "Update a lead's stage or deal_value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["new", "contacted", "qualified", "follow_up", "won", "lost"]},
                    "deal_value": {"type": "number"},
                },
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_assign_lead",
            "description": "Auto-assign a lead to the least-loaded active sales rep.",
            "parameters": {
                "type": "object",
                "properties": {"lead_id": {"type": "integer"}},
                "required": ["lead_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_handoffs",
            "description": "List inbox conversations currently in the handoff queue.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_conversation",
            "description": "Send a staff reply into a conversation thread.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "integer"},
                    "content": {"type": "string"},
                },
                "required": ["conversation_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_outbox",
            "description": "Dispatch pending webhook outbox events.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_reminders",
            "description": "Run due test-drive appointment reminders.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the public web for latest vehicle specs, MSRP pricing, trims, EV models, or automotive news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Fetch and extract readable text from a public https/http URL found via web_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Public http/https URL"},
                },
                "required": ["url"],
            },
        },
    },
]


def _execute_tool(
    db: Session,
    dealership: Dealership,
    current_user: User,
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        if name == "get_dashboard_summary":
            return reporting_service.get_dealership_report_summary(db, dealership.id)

        if name == "list_vehicles":
            items = vehicle_service.list_vehicles(db, dealership.id, current_user)
            return {
                "vehicles": [
                    {
                        "id": v.id,
                        "year": v.model_year,
                        "make": v.make,
                        "model": v.model,
                        "variant": v.variant,
                        "price": float(v.price),
                        "stock_number": v.stock_number,
                        "status": v.status,
                        "test_drive_enabled": v.test_drive_enabled,
                    }
                    for v in items[:25]
                ]
            }

        if name == "create_vehicle":
            brand = _resolve_or_create_brand(db, dealership.id, current_user, str(args["make"]))
            v = vehicle_service.create_vehicle(
                db,
                dealership.id,
                current_user,
                VehicleCreateRequest(
                    brand_id=brand.id,
                    model=str(args["model"]),
                    model_year=int(args["model_year"]),
                    price=Decimal(str(args["price"])),
                    stock_number=str(args["stock_number"]),
                    variant=args.get("variant"),
                    description=args.get("description"),
                ),
            )
            if args.get("test_drive_enabled"):
                v = vehicle_service.update_vehicle(
                    db, dealership.id, v.id, current_user, VehicleUpdateRequest(test_drive_enabled=True)
                )
            _invalidate_dealership_caches(dealership.id)
            return {"created_vehicle": {"id": v.id, "make": v.make, "model": v.model, "year": v.model_year, "price": float(v.price), "stock_number": v.stock_number}}

        if name == "update_vehicle":
            v = _find_vehicle(
                db,
                dealership.id,
                vehicle_id=args.get("vehicle_id"),
                stock_number=args.get("stock_number"),
            )
            if v is None:
                return {"error": "Vehicle not found"}
            if args.get("price") is not None or args.get("test_drive_enabled") is not None:
                v = vehicle_service.update_vehicle(
                    db,
                    dealership.id,
                    v.id,
                    current_user,
                    VehicleUpdateRequest(
                        price=Decimal(str(args["price"])) if args.get("price") is not None else None,
                        test_drive_enabled=args.get("test_drive_enabled"),
                    ),
                )
            if args.get("status"):
                v = vehicle_service.transition_vehicle_status(
                    db,
                    dealership.id,
                    v.id,
                    current_user,
                    VehicleStatusTransitionRequest(status=str(args["status"]), notes="Updated via AI Agent"),
                )
            _invalidate_dealership_caches(dealership.id)
            return {"updated_vehicle": {"id": v.id, "status": v.status, "price": float(v.price), "test_drive_enabled": v.test_drive_enabled}}

        if name == "delete_vehicle":
            v = _find_vehicle(
                db,
                dealership.id,
                vehicle_id=args.get("vehicle_id"),
                stock_number=args.get("stock_number"),
            )
            if v is None:
                return {"error": "Vehicle not found"}
            vehicle_service.delete_vehicle(db, dealership.id, v.id, current_user)
            _invalidate_dealership_caches(dealership.id)
            return {"deleted_vehicle_id": v.id}

        if name == "create_brand":
            b = brand_service.create_brand(db, dealership.id, current_user, BrandCreateRequest(name=str(args["name"])))
            _invalidate_dealership_caches(dealership.id)
            return {"created_brand": {"id": b.id, "name": b.name}}

        if name == "list_slots":
            slots = test_drive_service.list_slots(db, dealership.id, vehicle_id=args.get("vehicle_id"))
            return {
                "slots": [
                    {
                        "id": s.id,
                        "vehicle_id": s.vehicle_id,
                        "starts_at": s.starts_at.isoformat(),
                        "capacity": s.capacity,
                        "booked_count": s.booked_count,
                        "is_active": s.is_active,
                    }
                    for s in slots[:25]
                ]
            }

        if name == "create_slot":
            starts = datetime.fromisoformat(str(args["starts_at_iso"]).replace("Z", "+00:00"))
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=timezone.utc)
            dur = int(args.get("duration_minutes") or 30)
            slot = test_drive_service.create_slot(
                db,
                dealership.id,
                current_user,
                TestDriveSlotCreateRequest(
                    vehicle_id=int(args["vehicle_id"]),
                    starts_at=starts,
                    ends_at=starts + timedelta(minutes=dur),
                    capacity=int(args.get("capacity") or 1),
                ),
            )
            return {"created_slot": {"id": slot.id, "vehicle_id": slot.vehicle_id, "starts_at": slot.starts_at.isoformat(), "capacity": slot.capacity}}

        if name == "generate_slots":
            days = max(1, min(30, int(args.get("days") or 7)))
            start = datetime.now(ZoneInfo(dealership.timezone or "UTC")).date()
            end = start + timedelta(days=days)
            slots = test_drive_service.generate_slots(db, dealership.id, current_user, start_date=start, end_date=end)
            return {"generated_count": len(slots), "start_date": start.isoformat(), "end_date": end.isoformat()}

        if name == "update_slot":
            slot = test_drive_service.update_slot(
                db,
                dealership.id,
                int(args["slot_id"]),
                current_user,
                TestDriveSlotUpdateRequest(capacity=args.get("capacity"), is_active=args.get("is_active")),
            )
            return {"updated_slot": {"id": slot.id, "capacity": slot.capacity, "is_active": slot.is_active}}

        if name == "update_booking_outcome":
            b = test_drive_service.update_booking_outcome(
                db,
                dealership.id,
                int(args["booking_id"]),
                current_user,
                TestDriveBookingOutcomeRequest(status=str(args["status"]), outcome_notes=args.get("outcome_notes")),
            )
            return {"updated_booking": {"id": b.id, "status": b.status}}

        if name == "list_leads":
            leads = lead_service.list_leads(db, dealership.id, current_user, status=args.get("status"))
            return {
                "leads": [
                    {"id": l.id, "name": l.name, "email": l.email, "status": l.status, "deal_value": float(l.deal_value) if l.deal_value is not None else None}
                    for l in leads[:20]
                ]
            }

        if name == "create_lead":
            lead = lead_service.create_lead(
                db,
                dealership.id,
                CustomerLeadCreateRequest(
                    name=str(args["name"]),
                    email=str(args["email"]),
                    phone=args.get("phone"),
                    message=str(args["message"]),
                    source="phone",
                    consent_to_contact=True,
                ),
                current_user,
            )
            _invalidate_dealership_caches(dealership.id)
            return {"created_lead": {"id": lead.id, "name": lead.name, "email": lead.email}}

        if name == "update_lead":
            lead = lead_service.update_lead(
                db,
                dealership.id,
                int(args["lead_id"]),
                current_user,
                CustomerLeadUpdateRequest(
                    status=args.get("status"),
                    deal_value=Decimal(str(args["deal_value"])) if args.get("deal_value") is not None else None,
                ),
            )
            _invalidate_dealership_caches(dealership.id)
            return {"updated_lead": {"id": lead.id, "status": lead.status}}

        if name == "auto_assign_lead":
            lead = lead_service.auto_assign_lead(db, dealership.id, int(args["lead_id"]), current_user)
            return {"assigned_lead": {"id": lead.id, "assigned_to_user_id": lead.assigned_to_user_id}}

        if name == "list_handoffs":
            convs = conversation_service.list_conversations(db, dealership.id, status="handed_off", page=1, page_size=10)
            return {"handoffs": [{"id": c.id, "channel": c.channel, "channel_user_id": c.channel_user_id} for c in convs]}

        if name == "reply_conversation":
            conversation_service.add_staff_reply(db, dealership.id, int(args["conversation_id"]), current_user, str(args["content"]))
            return {"replied_conversation_id": int(args["conversation_id"])}

        if name == "dispatch_outbox":
            return outbox_service.dispatch_pending_outbox_events(db, dealership_id=dealership.id)

        if name == "run_reminders":
            return reminder_service.process_due_booking_reminders(db, dealership_id=dealership.id)

        if name == "web_search":
            return _tool_web_search(
                str(args["query"]),
                max_results=max(1, min(8, int(args.get("max_results") or 5))),
            )

        if name == "fetch_webpage":
            return _tool_fetch_webpage(str(args["url"]))

        return {"error": f"Unknown tool: {name}"}
    except ApplicationError as exc:
        return {"error": exc.detail}
    except Exception as exc:
        logger.warning("Tool %s error: %s", name, exc)
        return {"error": str(exc)}


def run_llm_staff_agent(
    db: Session,
    dealership: Dealership,
    current_user: User | None,
    message: str,
    conversation_history: list[Any] | None = None,
) -> dict[str, Any] | None:
    """
    LLM-first Dealership Operations Agent:
    1. Sends the user's prompt + live dealership context + tools directly to the configured LLM (Groq/OpenAI).
    2. Executes any requested CRM tools with full RBAC enforcement.
    3. Applies the output safety layer (`sanitize_output`) before returning.
    Falls back to deterministic `try_execute_staff_action` if no LLM is configured or if the LLM call fails.
    """
    if not _is_staff(current_user) or current_user is None:
        return None

    # Handle batch CSV/JSON uploads deterministically first so large files don't blow token limits
    if _extract_json_records(message) is not None or _extract_csv_records(message) is not None:
        return try_execute_staff_action(db, dealership, current_user, message)

    llm_cfg = get_settings().get_llm_config()
    if llm_cfg is None:
        return try_execute_staff_action(db, dealership, current_user, message)

    llm_url, llm_key, primary_model, fallback_model = llm_cfg

    brands = db.scalars(
        select(Brand).where(Brand.dealership_id == dealership.id, Brand.is_deleted.is_(False))
    ).all()
    vehicles = db.scalars(
        select(Vehicle).where(Vehicle.dealership_id == dealership.id).limit(15)
    ).all()

    system_prompt = (
        f"You are the internal Dealership Operations AI Agent for '{dealership.name}' "
        f"(timezone: {dealership.timezone}, logged-in staff: {current_user.name}, role: {current_user.role}).\n"
        f"Current UTC time: {datetime.now(timezone.utc).isoformat()}.\n"
        f"Existing brands: {', '.join(b.name for b in brands) or 'None'}.\n"
        f"Sample vehicles: {', '.join(f'#{v.id} {v.model_year} {v.make} {v.model} (${float(v.price):,.0f}, Stock {v.stock_number}, {v.status})' for v in vehicles) or 'None'}.\n"
        "You can answer questions AND perform real CRM actions using your tools (vehicles, brands, test-drive slots, bookings, leads, inbox handoffs, outbox, reminders).\n"
        "You also have `web_search` and `fetch_webpage` tools to look up the latest vehicle specs, MSRP pricing, trims, and industry information when needed.\n"
        "If the user wants to add a vehicle or perform an action but required details are missing (like price or stock number), politely ask for the missing fields or use `web_search` if they asked you to look up specs/pricing first. "
        "Never invent tool results—always call the tool first."
    )

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for item in (conversation_history or [])[-6:]:
        role = getattr(item, "role", None) or (item.get("role") if isinstance(item, dict) else "user")
        content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else "")
        if content:
            messages.append({"role": "assistant" if role == "assistant" else "user", "content": str(content)})
    messages.append({"role": "user", "content": message})

    any_tool_called = False
    models_to_try = [primary_model] + ([fallback_model] if fallback_model and fallback_model != primary_model else [])

    for model_name in models_to_try:
        try:
            with httpx.Client(timeout=25.0) as client:
                working_msgs = list(messages)
                for _ in range(4):
                    resp = client.post(
                        llm_url,
                        json={
                            "model": model_name,
                            "messages": working_msgs,
                            "tools": _AGENT_TOOLS,
                            "tool_choice": "auto",
                            "temperature": 0.2,
                            "max_tokens": 900,
                        },
                        headers={
                            "Authorization": f"Bearer {llm_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning("LLM agent HTTP %d with model %s: %s", resp.status_code, model_name, resp.text[:250])
                        break

                    choice = resp.json()["choices"][0]["message"]
                    tool_calls = choice.get("tool_calls") or []
                    if not tool_calls:
                        raw_text = (choice.get("content") or "").strip()
                        if not raw_text:
                            break
                        safe_text = sanitize_output(raw_text, dealership_name=dealership.name)
                        return {
                            "intent": "agent_action" if any_tool_called else "assistant_response",
                            "response": safe_text,
                            "suggested_actions": [],
                        }

                    any_tool_called = True
                    working_msgs.append(choice)
                    for tc in tool_calls:
                        fn_name = tc["function"]["name"]
                        try:
                            fn_args = json.loads(tc["function"].get("arguments") or "{}")
                        except json.JSONDecodeError:
                            fn_args = {}
                        tool_result = _execute_tool(db, dealership, current_user, fn_name, fn_args)
                        working_msgs.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(tool_result, default=str),
                            }
                        )
        except Exception as exc:
            logger.warning("LLM agent call failed with model %s: %s", model_name, exc)

    return try_execute_staff_action(db, dealership, current_user, message)


def _is_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
            return False
        addr_info = socket.getaddrinfo(host, None)
        for info in addr_info:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def _strip_html(raw: str) -> str:
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>[\s\S]*?</\1>", " ", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _tool_web_search(query: str, *, max_results: int = 5) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DealerDeskAgent/1.0)"}
    results: list[dict[str, str]] = []
    with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
        try:
            resp = client.get(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}")
            if resp.status_code == 200:
                blocks = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?(?:<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)</a>)?',
                    resp.text,
                )
                for href, title_html, snip_html in blocks[:max_results]:
                    results.append(
                        {
                            "title": _strip_html(title_html),
                            "url": html.unescape(href),
                            "snippet": _strip_html(snip_html or ""),
                        }
                    )
        except Exception as exc:
            logger.warning("DuckDuckGo HTML search failed for %r: %s", query, exc)

        if not results:
            try:
                wiki = client.get(
                    f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(query)}&format=json&srlimit={max_results}"
                )
                if wiki.status_code == 200:
                    for item in wiki.json().get("query", {}).get("search", [])[:max_results]:
                        title = item.get("title", "")
                        results.append(
                            {
                                "title": title,
                                "url": f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
                                "snippet": _strip_html(item.get("snippet", "")),
                            }
                        )
            except Exception as exc:
                logger.warning("Wikipedia fallback search failed for %r: %s", query, exc)

    if not results:
        return {"query": query, "results": [], "note": "No live search results returned."}
    return {"query": query, "results": results[:max_results]}


def _tool_fetch_webpage(url: str) -> dict[str, Any]:
    if not _is_public_url(url):
        return {"error": "Blocked or invalid URL (only public http/https URLs are allowed)."}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DealerDeskAgent/1.0)"}
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code >= 400:
                return {"error": f"HTTP {resp.status_code} fetching {url}"}
            text = _strip_html(resp.text)
            return {"url": str(resp.url), "content": text[:4000]}
    except Exception as exc:
        return {"error": f"Could not fetch URL: {exc}"}
