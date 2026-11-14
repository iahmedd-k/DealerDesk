import json
import urllib.error
import urllib.request

from app.core.config import get_settings


def send_staff_invitation(
    *,
    recipient: str,
    dealership_name: str,
    temporary_password: str,
    activation_token: str,
) -> str:
    settings = get_settings()
    if settings.resend_api_key is None:
        return "email_provider_pending"

    payload = {
        "from": settings.resend_from_email,
        "to": [recipient],
        "subject": f"Your {dealership_name} staff account",
        "text": (
            f"You have been invited to {dealership_name}.\n\n"
            f"Temporary password: {temporary_password}\n"
            f"Activation token: {activation_token}\n\n"
            "Sign in and change this temporary password immediately."
        ),
    }
    if settings.resend_reply_to:
        payload["reply_to"] = [settings.resend_reply_to]
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in {200, 201}:
                return "email_delivery_failed"
    except (OSError, urllib.error.HTTPError):
        return "email_delivery_failed"
    return "email_sent"
