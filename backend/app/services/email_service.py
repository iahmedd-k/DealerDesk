import html
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 0.5


def _is_deliverable_email(email: str | None) -> bool:
    if not email or "@" not in email:
        return False
    normalized = email.strip().lower()
    if normalized.endswith(".local"):
        return False
    return True


def _send_resend_email(payload: dict[str, Any]) -> str:
    settings = get_settings()
    if "from" not in payload or not payload["from"]:
        payload["from"] = settings.resend_from_email

    recipients = payload.get("to") or []
    deliverable = [r for r in recipients if _is_deliverable_email(r)]
    if not deliverable:
        return "email_skipped_synthetic"
    payload["to"] = deliverable

    if (
        settings.resend_api_key is None
        or not settings.resend_api_key.get_secret_value()
    ):
        return "email_provider_pending"

    if settings.resend_reply_to and "reply_to" not in payload:
        payload["reply_to"] = [settings.resend_reply_to]

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=data,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status in {200, 201}:
                    return "email_sent"
                logger.warning(
                    "Resend HTTP %d on attempt %d for recipient %s",
                    response.status,
                    attempt,
                    payload.get("to"),
                )
        except (OSError, urllib.error.HTTPError) as exc:
            last_error = exc
            logger.warning(
                "Email delivery attempt %d/%d failed: %s",
                attempt,
                MAX_RETRIES,
                exc,
            )

        if attempt < MAX_RETRIES:
            time.sleep(INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    logger.error(
        "email_delivery_dead_letter",
        extra={
            "recipient": payload.get("to"),
            "subject": payload.get("subject"),
            "error": str(last_error),
        },
    )
    return "email_delivery_failed"


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _detail_row(label: str, value: str) -> str:
    return (
        "<tr>"
        '<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#64748b;'
        'font-size:13px;font-weight:600;width:36%;vertical-align:top;">'
        f"{_esc(label)}</td>"
        '<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;'
        'font-size:13px;vertical-align:top;">'
        f"{_esc(value)}</td>"
        "</tr>"
    )


def _details_table(rows: list[tuple[str, str]]) -> str:
    inner = "".join(_detail_row(label, value) for label, value in rows)
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:18px 0;border:1px solid #e2e8f0;border-radius:8px;'
        'border-collapse:collapse;background-color:#f8fafc;">'
        f"{inner}</table>"
    )


def _code_box(label: str, code: str) -> str:
    return (
        '<div style="margin:18px 0;padding:16px;border-radius:8px;'
        'background-color:#f1f5f9;border:1px solid #cbd5e1;text-align:center;">'
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:#475569;margin-bottom:6px;">{_esc(label)}</div>'
        f'<div style="font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;'
        f'font-size:18px;font-weight:700;color:#0f172a;word-break:break-all;">{_esc(code)}</div>'
        "</div>"
    )


def _render_email_layout(
    *,
    title: str,
    preheader: str,
    body_html: str,
    badge: str | None = None,
    badge_bg: str = "#dbeafe",
    badge_fg: str = "#1e40af",
    footer_note: str | None = None,
) -> str:
    badge_html = ""
    if badge:
        badge_html = (
            f'<div style="display:inline-block;padding:4px 10px;border-radius:9999px;'
            f'background-color:{badge_bg};color:{badge_fg};font-size:11px;'
            f'font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:12px;">'
            f"{_esc(badge)}</div>"
        )
    footer_extra = (
        f'<p style="margin:0 0 8px 0;color:#64748b;font-size:12px;">{_esc(footer_note)}</p>'
        if footer_note
        else ""
    )
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0" />'
        f"<title>{_esc(title)}</title>"
        "</head>"
        '<body style="margin:0;padding:0;background-color:#f1f5f9;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;\">"
        f'<div style="display:none;max-height:0;overflow:hidden;">{_esc(preheader)}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#f1f5f9;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;background-color:#ffffff;border-radius:12px;'
        'overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(15,23,42,0.06);">'
        '<tr><td style="background-color:#0f172a;padding:22px 28px;">'
        '<div style="font-size:18px;font-weight:800;color:#ffffff;letter-spacing:-0.02em;">'
        'Dealer<span style="color:#3b82f6;">Desk</span>'
        "</div>"
        '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">'
        "Dealership Operations &amp; Customer Experience"
        "</div>"
        "</td></tr>"
        '<tr><td style="padding:28px;">'
        f"{badge_html}"
        f'<h1 style="margin:0 0 14px 0;font-size:20px;font-weight:700;color:#0f172a;line-height:1.3;">'
        f"{_esc(title)}</h1>"
        f'<div style="font-size:14px;line-height:1.6;color:#334155;">{body_html}</div>'
        "</td></tr>"
        '<tr><td style="background-color:#f8fafc;padding:18px 28px;border-top:1px solid #e2e8f0;">'
        f"{footer_extra}"
        '<p style="margin:0;color:#94a3b8;font-size:11px;">'
        "This is an automated message from DealerDesk. Please do not share sensitive credentials or tokens."
        "</p>"
        "</td></tr>"
        "</table>"
        "</td></tr>"
        "</table>"
        "</body></html>"
    )


def send_staff_invitation(
    *,
    recipient: str,
    dealership_name: str,
    temporary_password: str,
    activation_token: str,
) -> str:
    settings = get_settings()
    subject = f"You're invited to join {dealership_name} on DealerDesk"
    text_body = (
        f"You have been invited to {dealership_name}.\n\n"
        f"Temporary password: {temporary_password}\n"
        f"Activation token: {activation_token}\n\n"
        "Sign in and change this temporary password immediately."
    )
    body_html = (
        f"<p>You have been invited to join <strong>{_esc(dealership_name)}</strong> on DealerDesk.</p>"
        "<p>Use the credentials below to activate your staff account. For your security, "
        "please sign in and change your temporary password immediately.</p>"
        + _code_box("Temporary Password", temporary_password)
        + _code_box("Activation Token", activation_token)
    )
    html_body = _render_email_layout(
        title=f"Welcome to {dealership_name}",
        preheader=f"Your {dealership_name} staff account is ready for activation.",
        badge="Staff Invitation",
        body_html=body_html,
        footer_note="This invitation expires in 48 hours.",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_password_reset(*, recipient: str, reset_token: str) -> str:
    settings = get_settings()
    subject = "Reset your DealerDesk password"
    text_body = (
        "A password reset was requested for your DealerDesk account.\n\n"
        f"Reset token: {reset_token}\n"
        "This token expires in one hour."
    )
    body_html = (
        "<p>We received a request to reset the password for your DealerDesk account.</p>"
        "<p>Enter the reset token below to choose a new password:</p>"
        + _code_box("Password Reset Token", reset_token)
        + "<p style='color:#64748b;font-size:13px;'>If you did not request a password reset, "
        "you can safely ignore this email—your password will remain unchanged.</p>"
    )
    html_body = _render_email_layout(
        title="Password Reset Request",
        preheader="Use this token to reset your DealerDesk password.",
        badge="Security",
        badge_bg="#fef3c7",
        badge_fg="#92400e",
        body_html=body_html,
        footer_note="This reset token expires in 1 hour.",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_email_verification(*, recipient: str, verification_token: str) -> str:
    settings = get_settings()
    subject = "Verify your DealerDesk email address"
    text_body = (
        "Thank you for registering with DealerDesk.\n\n"
        f"Verification token: {verification_token}\n"
        "This token expires in 24 hours. Please verify your email to unlock all features."
    )
    body_html = (
        "<p>Thank you for registering with <strong>DealerDesk</strong>.</p>"
        "<p>Please verify your email address using the verification token below to unlock all account features:</p>"
        + _code_box("Email Verification Token", verification_token)
    )
    html_body = _render_email_layout(
        title="Verify Your Email Address",
        preheader="Confirm your email address to activate your DealerDesk account.",
        badge="Account Verification",
        body_html=body_html,
        footer_note="This verification token expires in 24 hours.",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_otp_email(
    *,
    recipient: str,
    code: str,
    expires_minutes: int = 5,
    purpose: str = "test-drive booking verification",
) -> str:
    settings = get_settings()
    subject = f"Your DealerDesk Verification Code: {code}"
    text_body = (
        f"Your verification code for {purpose} is: {code}\n\n"
        f"This code will expire in {expires_minutes} minutes. "
        "If you did not request this, please disregard this message."
    )
    body_html = (
        f"<p>Use the one-time verification code below to complete your <strong>{_esc(purpose)}</strong>:</p>"
        + _code_box("One-Time Verification Code", code)
        + f"<p style='color:#64748b;font-size:13px;'>This code expires in {expires_minutes} minutes. "
        "If you did not request this code, please ignore this email.</p>"
    )
    html_body = _render_email_layout(
        title="Verification Code",
        preheader=f"Your DealerDesk verification code is {code}.",
        badge="One-Time Passcode",
        body_html=body_html,
        footer_note=f"Valid for {expires_minutes} minutes.",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_password_changed_alert(
    *,
    recipient: str,
    user_name: str | None = None,
) -> str:
    settings = get_settings()
    greeting = f"Hi {user_name}," if user_name else "Hello,"
    subject = "Your DealerDesk password was changed"
    text_body = (
        f"{greeting}\n\n"
        "This is a confirmation that the password for your DealerDesk account was recently changed.\n"
        "If you made this change, no further action is needed. If you did not authorize this change, "
        "please reset your password immediately and contact support."
    )
    body_html = (
        f"<p>{_esc(greeting)}</p>"
        "<p>This is a security confirmation that the password for your DealerDesk account was recently updated.</p>"
        "<p>If you made this change, no further action is required. If you did not authorize this change, "
        "please reset your password immediately or contact your dealership administrator.</p>"
    )
    html_body = _render_email_layout(
        title="Password Updated",
        preheader="Security notice: your DealerDesk password was changed.",
        badge="Security Alert",
        badge_bg="#fee2e2",
        badge_fg="#991b1b",
        body_html=body_html,
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_dealership_welcome(
    *,
    recipient: str,
    admin_name: str,
    dealership_name: str,
    dealership_email: str,
    timezone_name: str,
) -> str:
    settings = get_settings()
    subject = f"Welcome to DealerDesk — {dealership_name} is live"
    text_body = (
        f"Hi {admin_name},\n\n"
        f"Your dealership workspace '{dealership_name}' has been created on DealerDesk.\n\n"
        f"Dealership Email: {dealership_email}\n"
        f"Timezone: {timezone_name}\n\n"
        "You can now sign in to manage brands, vehicle inventory, test-drive schedules, leads, and AI channels."
    )
    body_html = (
        f"<p>Hi <strong>{_esc(admin_name)}</strong>,</p>"
        f"<p>Your dealership workspace <strong>{_esc(dealership_name)}</strong> is now active on DealerDesk.</p>"
        + _details_table(
            [
                ("Dealership", dealership_name),
                ("Contact Email", dealership_email),
                ("Timezone", timezone_name),
                ("Admin Account", recipient),
            ]
        )
        + "<p>Sign in to configure your vehicle inventory, test-drive availability, knowledge base, and AI sales channels.</p>"
    )
    html_body = _render_email_layout(
        title=f"Welcome to DealerDesk, {dealership_name}!",
        preheader=f"Your dealership workspace {dealership_name} is ready.",
        badge="Workspace Created",
        badge_bg="#dcfce7",
        badge_fg="#166534",
        body_html=body_html,
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_test_drive_confirmation(
    *,
    recipient: str,
    customer_name: str,
    dealership_name: str,
    dealership_address: str | None,
    dealership_phone: str | None,
    vehicle_label: str,
    stock_number: str | None,
    starts_at_local: str,
    ends_at_local: str,
    timezone_name: str,
    booking_id: int,
) -> str:
    settings = get_settings()
    subject = f"Test Drive Confirmed: {vehicle_label} at {dealership_name}"
    rows: list[tuple[str, str]] = [
        ("Booking Reference", f"#{booking_id}"),
        ("Vehicle", vehicle_label),
    ]
    if stock_number:
        rows.append(("Stock #", stock_number))
    rows.extend(
        [
            ("Date & Time", f"{starts_at_local} – {ends_at_local} ({timezone_name})"),
            ("Dealership", dealership_name),
        ]
    )
    if dealership_address:
        rows.append(("Location", dealership_address))
    if dealership_phone:
        rows.append(("Phone", dealership_phone))

    text_body = (
        f"Hi {customer_name},\n\n"
        f"Your test drive at {dealership_name} is confirmed!\n\n"
        f"Booking Reference: #{booking_id}\n"
        f"Vehicle: {vehicle_label}\n"
        f"When: {starts_at_local} - {ends_at_local} ({timezone_name})\n"
        + (f"Location: {dealership_address}\n" if dealership_address else "")
        + (f"Phone: {dealership_phone}\n" if dealership_phone else "")
        + "\nPlease bring a valid driver's license. We look forward to seeing you!"
    )
    body_html = (
        f"<p>Hi <strong>{_esc(customer_name)}</strong>,</p>"
        f"<p>Your test drive appointment at <strong>{_esc(dealership_name)}</strong> has been confirmed.</p>"
        + _details_table(rows)
        + "<p>Please bring a valid driver's license when you arrive. If you need to reschedule or cancel, "
        "you can manage your booking anytime in DealerDesk.</p>"
    )
    html_body = _render_email_layout(
        title="Test Drive Confirmed",
        preheader=f"Confirmed: {vehicle_label} on {starts_at_local}",
        badge="Booking Confirmed",
        badge_bg="#dcfce7",
        badge_fg="#166534",
        body_html=body_html,
        footer_note=f"Booking Reference #{booking_id} • {dealership_name}",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_test_drive_rescheduled(
    *,
    recipient: str,
    customer_name: str,
    dealership_name: str,
    dealership_address: str | None,
    vehicle_label: str,
    starts_at_local: str,
    ends_at_local: str,
    timezone_name: str,
    booking_id: int,
) -> str:
    settings = get_settings()
    subject = f"Test Drive Rescheduled: {vehicle_label} (#{booking_id})"
    rows: list[tuple[str, str]] = [
        ("Booking Reference", f"#{booking_id}"),
        ("Vehicle", vehicle_label),
        ("New Date & Time", f"{starts_at_local} – {ends_at_local} ({timezone_name})"),
        ("Dealership", dealership_name),
    ]
    if dealership_address:
        rows.append(("Location", dealership_address))

    text_body = (
        f"Hi {customer_name},\n\n"
        f"Your test drive booking (#{booking_id}) at {dealership_name} has been rescheduled.\n\n"
        f"Vehicle: {vehicle_label}\n"
        f"New Time: {starts_at_local} - {ends_at_local} ({timezone_name})\n"
        + (f"Location: {dealership_address}\n" if dealership_address else "")
    )
    body_html = (
        f"<p>Hi <strong>{_esc(customer_name)}</strong>,</p>"
        f"<p>Your test drive appointment at <strong>{_esc(dealership_name)}</strong> has been updated to a new time slot.</p>"
        + _details_table(rows)
        + "<p>Please bring a valid driver's license to your appointment.</p>"
    )
    html_body = _render_email_layout(
        title="Test Drive Rescheduled",
        preheader=f"Updated time for {vehicle_label}: {starts_at_local}",
        badge="Booking Updated",
        badge_bg="#dbeafe",
        badge_fg="#1e40af",
        body_html=body_html,
        footer_note=f"Booking Reference #{booking_id} • {dealership_name}",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_test_drive_cancelled(
    *,
    recipient: str,
    customer_name: str,
    dealership_name: str,
    vehicle_label: str,
    starts_at_local: str,
    timezone_name: str,
    booking_id: int,
) -> str:
    settings = get_settings()
    subject = f"Test Drive Cancelled: {vehicle_label} (#{booking_id})"
    rows = [
        ("Booking Reference", f"#{booking_id}"),
        ("Vehicle", vehicle_label),
        ("Original Time", f"{starts_at_local} ({timezone_name})"),
        ("Dealership", dealership_name),
        ("Status", "Cancelled"),
    ]
    text_body = (
        f"Hi {customer_name},\n\n"
        f"Your test drive booking (#{booking_id}) for the {vehicle_label} at {dealership_name} "
        f"scheduled for {starts_at_local} ({timezone_name}) has been cancelled.\n\n"
        "You can book a new time slot whenever you are ready."
    )
    body_html = (
        f"<p>Hi <strong>{_esc(customer_name)}</strong>,</p>"
        f"<p>Your test drive appointment at <strong>{_esc(dealership_name)}</strong> has been cancelled.</p>"
        + _details_table(rows)
        + "<p>If you'd like to schedule another appointment, feel free to pick a new time slot anytime.</p>"
    )
    html_body = _render_email_layout(
        title="Test Drive Cancelled",
        preheader=f"Booking #{booking_id} for {vehicle_label} was cancelled.",
        badge="Cancelled",
        badge_bg="#f1f5f9",
        badge_fg="#475569",
        body_html=body_html,
        footer_note=f"Booking Reference #{booking_id} • {dealership_name}",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_test_drive_reminder(
    *,
    recipient: str,
    customer_name: str,
    dealership_name: str,
    dealership_address: str | None,
    dealership_phone: str | None,
    vehicle_label: str,
    stock_number: str | None,
    starts_at_local: str,
    ends_at_local: str,
    timezone_name: str,
    booking_id: int,
    hours_before: int = 24,
) -> str:
    settings = get_settings()
    window_label = f"{hours_before} Hours" if hours_before > 1 else "Soon"
    subject = f"Reminder: Your Test Drive ({vehicle_label}) at {dealership_name}"
    rows: list[tuple[str, str]] = [
        ("Booking Reference", f"#{booking_id}"),
        ("Vehicle", vehicle_label),
    ]
    if stock_number:
        rows.append(("Stock #", stock_number))
    rows.extend(
        [
            ("Date & Time", f"{starts_at_local} – {ends_at_local} ({timezone_name})"),
            ("Dealership", dealership_name),
        ]
    )
    if dealership_address:
        rows.append(("Location", dealership_address))
    if dealership_phone:
        rows.append(("Phone", dealership_phone))

    text_body = (
        f"Hi {customer_name},\n\n"
        f"This is a friendly reminder about your upcoming test drive at {dealership_name}.\n\n"
        f"Booking Reference: #{booking_id}\n"
        f"Vehicle: {vehicle_label}\n"
        f"When: {starts_at_local} - {ends_at_local} ({timezone_name})\n"
        + (f"Location: {dealership_address}\n" if dealership_address else "")
        + (f"Phone: {dealership_phone}\n" if dealership_phone else "")
        + "\nPlease remember to bring a valid driver's license."
    )
    body_html = (
        f"<p>Hi <strong>{_esc(customer_name)}</strong>,</p>"
        f"<p>This is a friendly reminder about your upcoming test drive at <strong>{_esc(dealership_name)}</strong>.</p>"
        + _details_table(rows)
        + "<p>Please remember to bring a valid driver's license. Need to reschedule? You can update your appointment anytime in DealerDesk.</p>"
    )
    html_body = _render_email_layout(
        title="Upcoming Test Drive Reminder",
        preheader=f"Reminder ({window_label}): {vehicle_label} on {starts_at_local}",
        badge=f"Reminder · {window_label}",
        badge_bg="#dbeafe",
        badge_fg="#1e40af",
        body_html=body_html,
        footer_note=f"Booking Reference #{booking_id} • {dealership_name}",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_lead_acknowledgment(
    *,
    recipient: str,
    customer_name: str,
    dealership_name: str,
    dealership_phone: str | None,
    vehicle_label: str | None,
) -> str:
    settings = get_settings()
    subject = f"We received your inquiry — {dealership_name}"
    interest_line = f" regarding the {vehicle_label}" if vehicle_label else ""
    text_body = (
        f"Hi {customer_name},\n\n"
        f"Thank you for contacting {dealership_name}{interest_line}.\n"
        "A member of our sales team has received your inquiry and will reach out to you shortly.\n"
        + (f"\nNeed immediate assistance? Call us at {dealership_phone}." if dealership_phone else "")
    )
    rows: list[tuple[str, str]] = [("Dealership", dealership_name)]
    if vehicle_label:
        rows.append(("Vehicle of Interest", vehicle_label))
    if dealership_phone:
        rows.append(("Dealership Phone", dealership_phone))

    body_html = (
        f"<p>Hi <strong>{_esc(customer_name)}</strong>,</p>"
        f"<p>Thank you for reaching out to <strong>{_esc(dealership_name)}</strong>"
        f"{_esc(interest_line)}. Our team has received your request and will follow up with you shortly.</p>"
        + _details_table(rows)
    )
    html_body = _render_email_layout(
        title="Inquiry Received",
        preheader=f"Thank you for contacting {dealership_name}.",
        badge="Inquiry Confirmation",
        body_html=body_html,
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_new_lead_alert(
    *,
    recipient: str,
    dealership_name: str,
    lead_name: str,
    lead_email: str,
    lead_phone: str | None,
    source: str,
    vehicle_label: str | None,
    message: str,
) -> str:
    settings = get_settings()
    subject = f"New Customer Lead: {lead_name} ({source})"
    rows: list[tuple[str, str]] = [
        ("Customer", lead_name),
        ("Email", lead_email),
        ("Phone", lead_phone or "Not provided"),
        ("Source", source),
        ("Vehicle", vehicle_label or "General inquiry"),
        ("Message", message),
    ]
    text_body = (
        f"New lead captured for {dealership_name}:\n\n"
        f"Name: {lead_name}\n"
        f"Email: {lead_email}\n"
        f"Phone: {lead_phone or 'Not provided'}\n"
        f"Source: {source}\n"
        f"Vehicle: {vehicle_label or 'General inquiry'}\n"
        f"Message: {message}\n"
    )
    body_html = (
        f"<p>A new customer lead has been captured for <strong>{_esc(dealership_name)}</strong>.</p>"
        + _details_table(rows)
        + "<p>Sign in to the DealerDesk CRM dashboard to assign and follow up with this lead.</p>"
    )
    html_body = _render_email_layout(
        title=f"New Lead: {lead_name}",
        preheader=f"New {source} lead from {lead_name}",
        badge="New Lead Alert",
        badge_bg="#fef3c7",
        badge_fg="#92400e",
        body_html=body_html,
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )


def send_lead_assigned_notification(
    *,
    recipient: str,
    staff_name: str,
    dealership_name: str,
    lead_name: str,
    lead_email: str,
    lead_phone: str | None,
    vehicle_label: str | None,
    message: str,
    lead_id: int,
) -> str:
    settings = get_settings()
    subject = f"Lead Assigned to You: {lead_name} (#{lead_id})"
    rows = [
        ("Lead ID", f"#{lead_id}"),
        ("Customer", lead_name),
        ("Email", lead_email),
        ("Phone", lead_phone or "Not provided"),
        ("Vehicle", vehicle_label or "General inquiry"),
        ("Message", message),
    ]
    text_body = (
        f"Hi {staff_name},\n\n"
        f"A customer lead (#{lead_id}) at {dealership_name} has been assigned to you.\n\n"
        f"Customer: {lead_name}\n"
        f"Email: {lead_email}\n"
        f"Phone: {lead_phone or 'Not provided'}\n"
        f"Vehicle: {vehicle_label or 'General inquiry'}\n"
        f"Message: {message}\n"
    )
    body_html = (
        f"<p>Hi <strong>{_esc(staff_name)}</strong>,</p>"
        f"<p>A customer lead at <strong>{_esc(dealership_name)}</strong> has been assigned to you for follow-up.</p>"
        + _details_table(rows)
    )
    html_body = _render_email_layout(
        title=f"Lead Assigned: {lead_name}",
        preheader=f"Lead #{lead_id} ({lead_name}) assigned to you.",
        badge="Lead Assignment",
        body_html=body_html,
        footer_note=f"Lead #{lead_id} • {dealership_name}",
    )
    return _send_resend_email(
        {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    )
