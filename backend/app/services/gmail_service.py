import base64
import binascii
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from html.parser import HTMLParser
import logging
import os
import re
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from jwt import InvalidTokenError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    BadGatewayError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
)
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE
from app.models.channel import Conversation, ConversationMessage
from app.models.gmail import GmailMailboxConnection
from app.models.user import User
from app.models.workspace import Dealership
from app.services.conversation_service import scrub_sensitive_pii

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.send"
)
STATE_PURPOSE = "gmail_shared_mailbox"
MAX_INITIAL_THREADS = 50
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


class _HistoryExpired(Exception):
    pass


def _oauth_settings():
    settings = get_settings()
    if (
        not settings.google_oauth_client_id
        or not settings.google_oauth_client_secret
        or not settings.google_oauth_redirect_uri
        or not settings.jwt_secret_key
    ):
        raise ServiceUnavailableError(
            "Google Workspace mailbox integration is not configured."
        )
    _encryption_key()
    return settings


def _encryption_key() -> bytes:
    settings = get_settings()
    secret = settings.gmail_token_encryption_key
    if secret is None or not secret.get_secret_value():
        raise ServiceUnavailableError(
            "Gmail token encryption is not configured on the server."
        )
    encoded = secret.get_secret_value().strip()
    try:
        key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ServiceUnavailableError(
            "Gmail token encryption key must be URL-safe base64."
        ) from exc
    if len(key) != 32:
        raise ServiceUnavailableError(
            "Gmail token encryption key must encode exactly 32 bytes."
        )
    return key


def _encrypt_refresh_token(token: str, dealership_id: int) -> str:
    nonce = os.urandom(12)
    aad = f"dealerdesk:gmail:{dealership_id}:v1".encode("utf-8")
    ciphertext = AESGCM(_encryption_key()).encrypt(
        nonce,
        token.encode("utf-8"),
        aad,
    )
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_refresh_token(connection: GmailMailboxConnection) -> str:
    try:
        encoded = connection.encrypted_refresh_token.encode("ascii")
        payload = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
        nonce, ciphertext = payload[:12], payload[12:]
        aad = f"dealerdesk:gmail:{connection.dealership_id}:v1".encode("utf-8")
        return AESGCM(_encryption_key()).decrypt(nonce, ciphertext, aad).decode("utf-8")
    except (binascii.Error, InvalidTag, ValueError) as exc:
        raise ServiceUnavailableError(
            "The saved Gmail connection could not be decrypted. Reconnect the mailbox."
        ) from exc


def _state_token(user_id: int, dealership_id: int) -> str:
    settings = _oauth_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "purpose": STATE_PURPOSE,
            "sub": str(user_id),
            "dealership_id": dealership_id,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def create_authorization_url(user: User, dealership_id: int) -> str:
    settings = _oauth_settings()
    if (
        user.role not in {DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE}
        or user.dealership_id != dealership_id
    ):
        raise ForbiddenError("Only a dealership administrator or manager can connect email.")
    parameters = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": _state_token(user.id, dealership_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(parameters)}"


def frontend_redirect(path: str, **query: str) -> str:
    settings = get_settings()
    base = settings.frontend_base_url.rstrip("/")
    suffix = f"?{urlencode(query)}" if query else ""
    return f"{base}{path}{suffix}"


def _decode_state(state: str) -> tuple[int, int]:
    settings = _oauth_settings()
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
        if payload.get("purpose") != STATE_PURPOSE:
            raise InvalidTokenError("Unexpected OAuth state purpose")
        user_id = int(payload["sub"])
        dealership_id = int(payload["dealership_id"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise BadRequestError("The Google connection request expired. Please try again.") from exc
    return user_id, dealership_id


def _google_token_request(data: dict[str, str]) -> dict[str, Any]:
    try:
        response = httpx.post(GOOGLE_TOKEN_URL, data=data, timeout=20)
    except httpx.HTTPError as exc:
        logger.warning("Google OAuth token request could not reach Google: %s", type(exc).__name__)
        raise BadGatewayError("Could not reach Google to authorize the mailbox.") from exc
    if response.status_code >= 400:
        logger.warning("Google OAuth token request failed with HTTP %s", response.status_code)
        raise BadGatewayError("Google could not authorize the mailbox.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise BadGatewayError("Google returned an invalid authorization response.") from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise BadGatewayError("Google returned an incomplete authorization response.")
    return payload


def complete_authorization(db: Session, code: str, state: str) -> GmailMailboxConnection:
    user_id, dealership_id = _decode_state(state)
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    dealership = db.query(Dealership).filter(Dealership.id == dealership_id).first()
    if (
        user is None
        or dealership is None
        or not dealership.is_active
        or user.dealership_id != dealership_id
        or user.role not in {DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE}
    ):
        raise ForbiddenError("This account can no longer connect the dealership mailbox.")

    settings = _oauth_settings()
    tokens = _google_token_request(
        {
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret.get_secret_value(),
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
    )
    access_token = str(tokens["access_token"])
    existing = (
        db.query(GmailMailboxConnection)
        .filter(GmailMailboxConnection.dealership_id == dealership_id)
        .first()
    )
    refresh_token = tokens.get("refresh_token")
    profile = _gmail_request(access_token, "GET", "profile")
    gmail_address = str(profile.get("emailAddress", "")).strip().lower()
    if "@" not in gmail_address:
        raise BadGatewayError("Google did not return a valid mailbox address.")
    if not refresh_token and (
        existing is None or existing.gmail_address.lower() != gmail_address
    ):
        raise BadGatewayError(
            "Google did not provide a refresh token for this mailbox. Revoke DealerDesk access in Google and reconnect."
        )

    if existing is None:
        existing = GmailMailboxConnection(
            dealership_id=dealership_id,
            gmail_address=gmail_address,
            encrypted_refresh_token=_encrypt_refresh_token(
                str(refresh_token),
                dealership_id,
            ),
            connected_by_user_id=user.id,
        )
        db.add(existing)
    else:
        existing.gmail_address = gmail_address
        if refresh_token:
            existing.encrypted_refresh_token = _encrypt_refresh_token(
                str(refresh_token),
                dealership_id,
            )
        existing.connected_by_user_id = user.id
        existing.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(existing)
    return existing


def _get_connection(db: Session, dealership_id: int) -> GmailMailboxConnection:
    connection = (
        db.query(GmailMailboxConnection)
        .filter(GmailMailboxConnection.dealership_id == dealership_id)
        .first()
    )
    if connection is None:
        raise NotFoundError("No shared Gmail mailbox is connected.")
    return connection


def mailbox_status(db: Session, dealership_id: int) -> dict[str, Any]:
    connection = (
        db.query(GmailMailboxConnection)
        .filter(GmailMailboxConnection.dealership_id == dealership_id)
        .first()
    )
    return {
        "connected": connection is not None,
        "email": connection.gmail_address if connection else None,
        "last_synced_at": connection.last_synced_at if connection else None,
        "next_sync_at": connection.next_sync_at if connection else None,
        "last_sync_error": connection.last_sync_error if connection else None,
    }


def _refresh_access_token(connection: GmailMailboxConnection) -> str:
    settings = _oauth_settings()
    refresh_token = _decrypt_refresh_token(connection)
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret.get_secret_value(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
    except httpx.HTTPError as exc:
        logger.warning("Gmail token refresh could not reach Google: %s", type(exc).__name__)
        raise BadGatewayError("Could not reach Google to refresh the mailbox connection.") from exc
    if response.status_code >= 400:
        logger.warning("Gmail token refresh failed with HTTP %s", response.status_code)
        raise ServiceUnavailableError(
            "The Gmail connection has expired. Reconnect it in Settings."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise BadGatewayError("Google returned an invalid token refresh response.") from exc
    access_token = payload.get("access_token") if isinstance(payload, dict) else None
    if not access_token:
        raise BadGatewayError("Google returned an incomplete token refresh response.")
    return str(access_token)


def _gmail_request(
    access_token: str,
    method: str,
    resource: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = httpx.request(
            method,
            f"{GMAIL_API_URL}/{resource}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            json=json_body,
            timeout=20,
        )
    except httpx.HTTPError as exc:
        logger.warning("Gmail API request could not reach Google: %s", type(exc).__name__)
        raise BadGatewayError("Could not reach Google Gmail.") from exc
    if response.status_code == 401:
        raise ServiceUnavailableError(
            "The Gmail connection has expired. Reconnect it in Settings."
        )
    if response.status_code == 404 and resource == "history":
        raise _HistoryExpired
    if response.status_code == 429:
        raise ServiceUnavailableError("Google Gmail is temporarily rate-limiting requests.")
    if response.status_code >= 400:
        logger.warning(
            "Gmail API request to %s failed with HTTP %s",
            resource.split("/")[0],
            response.status_code,
        )
        raise BadGatewayError("Google Gmail could not complete the request.")
    if response.status_code == 204 or not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError as exc:
        raise BadGatewayError("Google Gmail returned an invalid response.") from exc
    if not isinstance(payload, dict):
        raise BadGatewayError("Google Gmail returned an unexpected response.")
    return payload


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError):
        return value


def _header(headers: list[dict[str, str]], name: str) -> str:
    target = name.lower()
    for item in headers:
        if item.get("name", "").lower() == target:
            return _decode_header(item.get("value"))
    return ""


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return ""


def _collect_body_parts(part: dict[str, Any], plain: list[str], html: list[str]) -> None:
    mime_type = str(part.get("mimeType", "")).lower()
    data = (part.get("body") or {}).get("data")
    filename = part.get("filename")
    if data and not filename:
        content = _decode_body(str(data))
        if mime_type == "text/plain":
            plain.append(content)
        elif mime_type == "text/html":
            html.append(content)
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            _collect_body_parts(child, plain, html)


def _text_from_payload(payload: dict[str, Any], snippet: str) -> str:
    plain: list[str] = []
    html: list[str] = []
    _collect_body_parts(payload, plain, html)
    if plain:
        return "\n".join(part for part in plain if part.strip()).strip()
    if html:
        parser = _HTMLTextParser()
        parser.feed("\n".join(html))
        rendered = " ".join(parser.parts)
        if rendered:
            return rendered
    return snippet.strip() or "(No text content)"


def _message_details(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    sender = parseaddr(_header(headers, "From"))[1].strip().lower()
    internal_date = message.get("internalDate")
    try:
        created_at = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        created_at = datetime.now(timezone.utc)
    return {
        "provider_id": str(message.get("id", "")),
        "sender": sender,
        "subject": _header(headers, "Subject"),
        "content": _text_from_payload(payload, str(message.get("snippet", ""))),
        "message_id": _header(headers, "Message-ID"),
        "in_reply_to": _header(headers, "In-Reply-To"),
        "references": _header(headers, "References"),
        "created_at": created_at,
        "attachments": _attachment_details(payload),
    }


def _attachment_details(payload: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []

    def collect(part: dict[str, Any]) -> None:
        filename = _decode_header(str(part.get("filename") or "")).strip()
        body = part.get("body") or {}
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            try:
                size = max(0, int(body.get("size", 0) or 0))
            except (TypeError, ValueError):
                size = 0
            attachments.append(
                {
                    "attachment_id": str(attachment_id),
                    "filename": filename,
                    "mime_type": str(part.get("mimeType") or "application/octet-stream"),
                    "size": size,
                }
            )
        for child in part.get("parts") or []:
            if isinstance(child, dict):
                collect(child)

    collect(payload)
    return attachments


def download_attachment(
    db: Session,
    dealership_id: int,
    conversation_message_id: int,
    attachment_id: str,
) -> tuple[bytes, str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", attachment_id):
        raise NotFoundError("Email attachment not found.")
    message = (
        db.query(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .filter(
            ConversationMessage.id == conversation_message_id,
            Conversation.dealership_id == dealership_id,
            Conversation.channel == "email",
        )
        .first()
    )
    if message is None:
        raise NotFoundError("Email attachment not found.")
    if not message.external_message_id:
        raise NotFoundError("Email attachment not found.")
    attachments = (message.channel_metadata or {}).get("attachments") or []
    attachment = next(
        (
            item
            for item in attachments
            if isinstance(item, dict) and item.get("attachment_id") == attachment_id
        ),
        None,
    )
    if attachment is None:
        raise NotFoundError("Email attachment not found.")
    try:
        declared_size = int(attachment.get("size", 0) or 0)
    except (TypeError, ValueError):
        declared_size = 0
    if declared_size > MAX_ATTACHMENT_BYTES:
        raise PayloadTooLargeError("Email attachments are limited to 20 MB.")

    connection = _get_connection(db, dealership_id)
    payload = _gmail_request(
        _refresh_access_token(connection),
        "GET",
        f"messages/{message.external_message_id}/attachments/{attachment_id}",
    )
    encoded = payload.get("data")
    if not isinstance(encoded, str):
        raise BadGatewayError("Google Gmail returned an invalid attachment.")
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        content = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError) as exc:
        raise BadGatewayError("Google Gmail returned an invalid attachment.") from exc
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise PayloadTooLargeError("Email attachments are limited to 20 MB.")
    return (
        content,
        str(attachment.get("mime_type") or "application/octet-stream"),
        str(attachment.get("filename") or "attachment"),
    )


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def sync_mailbox(db: Session, dealership_id: int) -> dict[str, int]:
    connection = _get_connection(db, dealership_id)
    access_token = _refresh_access_token(connection)
    thread_ids: set[str] = set()
    if connection.history_id:
        try:
            history = _gmail_request(
                access_token,
                "GET",
                "history",
                params={
                    "startHistoryId": connection.history_id,
                    "historyTypes": "messageAdded",
                    "maxResults": "100",
                },
            )
            while True:
                for record in history.get("history") or []:
                    for added in record.get("messagesAdded") or []:
                        message = added.get("message") or {}
                        thread_id = message.get("threadId")
                        if thread_id:
                            thread_ids.add(str(thread_id))
                next_history_id = str(history.get("historyId") or connection.history_id)
                page_token = history.get("nextPageToken")
                if not page_token:
                    break
                history = _gmail_request(
                    access_token,
                    "GET",
                    "history",
                    params={
                        "startHistoryId": connection.history_id,
                        "historyTypes": "messageAdded",
                        "maxResults": "100",
                        "pageToken": str(page_token),
                    },
                )
        except _HistoryExpired:
            connection.history_id = None

    if not connection.history_id:
        profile = _gmail_request(access_token, "GET", "profile")
        next_history_id = str(profile.get("historyId") or "")
        listing = _gmail_request(
            access_token,
            "GET",
            "threads",
            params={"maxResults": str(MAX_INITIAL_THREADS), "labelIds": "INBOX"},
        )
        thread_ids.update(
            str(item["id"])
            for item in listing.get("threads") or []
            if item.get("id")
        )

    imported_threads = 0
    imported_messages = 0

    for thread_id in thread_ids:
        thread_data = _gmail_request(
            access_token,
            "GET",
            f"threads/{thread_id}",
            params={"format": "full"},
        )
        raw_messages = thread_data.get("messages") or []
        raw_messages.sort(key=lambda item: int(item.get("internalDate", 0) or 0))
        details = [_message_details(item) for item in raw_messages]
        contact = next(
            (
                item["sender"]
                for item in details
                if item["sender"] and item["sender"] != connection.gmail_address.lower()
            ),
            None,
        )
        if not contact:
            continue

        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.dealership_id == dealership_id,
                Conversation.channel == "email",
                Conversation.external_thread_id == thread_id,
            )
            .first()
        )
        if conversation is None:
            first_time = details[0]["created_at"] if details else datetime.now(timezone.utc)
            conversation = Conversation(
                dealership_id=dealership_id,
                channel="email",
                channel_user_id=contact,
                external_thread_id=thread_id,
                status="active",
                channel_metadata={
                    "email_subject": next(
                        (item["subject"] for item in details if item["subject"]),
                        "(No subject)",
                    ),
                    "gmail_mailbox": connection.gmail_address,
                },
                created_at=first_time,
                updated_at=first_time,
            )
            db.add(conversation)
            db.flush()
            imported_threads += 1
        else:
            metadata = dict(conversation.channel_metadata or {})
            metadata["email_subject"] = next(
                (item["subject"] for item in details if item["subject"]),
                metadata.get("email_subject", "(No subject)"),
            )
            conversation.channel_metadata = metadata

        for item in details:
            provider_id = item["provider_id"]
            if not provider_id:
                continue
            exists = (
                db.query(ConversationMessage.id)
                .filter(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.external_message_id == provider_id,
                )
                .first()
            )
            if exists:
                continue
            content, scrubbed = scrub_sensitive_pii(item["content"])
            metadata: dict[str, Any] = {
                "provider": "gmail",
                "rfc822_message_id": item["message_id"],
                "in_reply_to": item["in_reply_to"],
                "references": item["references"],
                "attachments": item["attachments"],
            }
            if scrubbed:
                metadata["pii_scrubbed_on_ingest"] = True
            sender_type = (
                "staff"
                if item["sender"] == connection.gmail_address.lower()
                else "customer"
            )
            db.add(
                ConversationMessage(
                    conversation_id=conversation.id,
                    sender_type=sender_type,
                    sender_id=None,
                    content=content,
                    external_message_id=provider_id,
                    channel_metadata=metadata,
                    created_at=item["created_at"],
                )
            )
            conversation.updated_at = max(
                _utc_datetime(conversation.updated_at),
                item["created_at"],
            )
            if sender_type == "customer" and conversation.status == "closed":
                conversation.status = "active"
            imported_messages += 1

    connection.last_synced_at = datetime.now(timezone.utc)
    connection.next_sync_at = connection.last_synced_at + timedelta(minutes=5)
    connection.sync_attempts = 0
    connection.last_sync_error = None
    connection.history_id = next_history_id or connection.history_id
    connection.updated_at = connection.last_synced_at
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Another email sync is in progress. Try again shortly.") from exc
    return {"threads": imported_threads, "messages": imported_messages}


def send_reply(
    db: Session,
    conversation: Conversation,
    staff_user: User,
    content: str,
) -> dict[str, str]:
    if not conversation.external_thread_id:
        raise BadRequestError("This email thread cannot be replied to.")
    connection = _get_connection(db, conversation.dealership_id)
    recipient = parseaddr(conversation.channel_user_id)[1].strip()
    if "@" not in recipient:
        raise BadRequestError("The email thread does not have a valid reply address.")

    subject = str((conversation.channel_metadata or {}).get("email_subject") or "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}" if subject else "Re:"
    reply = EmailMessage()
    reply["To"] = recipient
    reply["From"] = connection.gmail_address
    reply["Subject"] = subject
    domain = connection.gmail_address.rsplit("@", 1)[-1]
    rfc822_id = make_msgid(domain=domain)

    previous_headers = [
        message.channel_metadata or {}
        for message in reversed(conversation.messages or [])
    ]
    previous_message_id = next(
        (meta.get("rfc822_message_id") for meta in previous_headers if meta.get("rfc822_message_id")),
        None,
    )
    references = next(
        (meta.get("references") for meta in previous_headers if meta.get("references")),
        None,
    )
    if previous_message_id:
        reply["In-Reply-To"] = str(previous_message_id)
        reply["References"] = f"{references} {previous_message_id}".strip() if references else str(previous_message_id)
    reply["Message-ID"] = rfc822_id
    reply.set_content(content.strip())

    raw = base64.urlsafe_b64encode(reply.as_bytes()).decode("ascii").rstrip("=")
    access_token = _refresh_access_token(connection)
    result = _gmail_request(
        access_token,
        "POST",
        "messages/send",
        json_body={"raw": raw, "threadId": conversation.external_thread_id},
    )
    provider_message_id = str(result.get("id", ""))
    if not provider_message_id:
        raise BadGatewayError("Google Gmail did not confirm delivery of the reply.")
    return {
        "provider_message_id": provider_message_id,
        "provider_thread_id": str(result.get("threadId", conversation.external_thread_id)),
        "rfc822_message_id": rfc822_id,
        "staff_email": staff_user.email,
        "references": reply.get("References", ""),
    }


def disconnect_mailbox(db: Session, dealership_id: int) -> None:
    connection = _get_connection(db, dealership_id)
    token = _decrypt_refresh_token(connection)
    try:
        response = httpx.post(
            GOOGLE_REVOKE_URL,
            data={"token": token},
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "Google token revocation returned HTTP %s during mailbox disconnect",
                response.status_code,
            )
    except httpx.HTTPError as exc:
        logger.warning("Google token revocation failed during disconnect: %s", type(exc).__name__)
    db.delete(connection)
    db.commit()
