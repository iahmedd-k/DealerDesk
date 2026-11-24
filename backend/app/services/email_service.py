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


def _send_resend_email(payload: dict[str, Any]) -> str:
    settings = get_settings()
    if (
        settings.resend_api_key is None
        or not settings.resend_api_key.get_secret_value()
    ):
        return "email_provider_pending"

    if settings.resend_reply_to:
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


def send_staff_invitation(
    *,
    recipient: str,
    dealership_name: str,
    temporary_password: str,
    activation_token: str,
) -> str:
    settings = get_settings()
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
    return _send_resend_email(payload)


def send_password_reset(*, recipient: str, reset_token: str) -> str:
    settings = get_settings()
    payload = {
        "from": settings.resend_from_email,
        "to": [recipient],
        "subject": "Reset your DealerDesk password",
        "text": (
            "A password reset was requested for your DealerDesk account.\n\n"
            f"Reset token: {reset_token}\n"
            "This token expires in one hour."
        ),
    }
    return _send_resend_email(payload)


def send_email_verification(*, recipient: str, verification_token: str) -> str:
    settings = get_settings()
    payload = {
        "from": settings.resend_from_email,
        "to": [recipient],
        "subject": "Verify your DealerDesk email address",
        "text": (
            "Thank you for registering with DealerDesk.\n\n"
            f"Verification token: {verification_token}\n"
            "This token expires in 24 hours. Please verify your email to unlock all features."
        ),
    }
    return _send_resend_email(payload)
