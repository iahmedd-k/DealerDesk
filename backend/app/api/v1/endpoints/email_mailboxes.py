import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.core.errors import ApplicationError
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.services import gmail_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Email mailbox"])


class GmailMailboxStatus(BaseModel):
    connected: bool
    email: str | None = None
    last_synced_at: datetime | None = None
    next_sync_at: datetime | None = None
    last_sync_error: str | None = None


class GmailAuthorizationURL(BaseModel):
    authorization_url: str


class GmailSyncResult(BaseModel):
    threads: int
    messages: int


@router.get(
    "/dealerships/{dealership_id}/email-mailbox",
    response_model=GmailMailboxStatus,
)
def get_mailbox_status(
    dealership_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return gmail_service.mailbox_status(db, dealership_id)


@router.post(
    "/dealerships/{dealership_id}/email-mailbox/connect",
    response_model=GmailAuthorizationURL,
)
def connect_mailbox(
    dealership_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
) -> GmailAuthorizationURL:
    return GmailAuthorizationURL(
        authorization_url=gmail_service.create_authorization_url(
            current_user,
            dealership_id,
        )
    )


@router.post(
    "/dealerships/{dealership_id}/email-mailbox/sync",
    response_model=GmailSyncResult,
)
def sync_mailbox(
    dealership_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> GmailSyncResult:
    result = gmail_service.sync_mailbox(db, dealership_id)
    return GmailSyncResult(**result)


@router.get(
    "/dealerships/{dealership_id}/email-mailbox/attachments/{message_id}/{attachment_id}",
    response_class=Response,
)
def download_email_attachment(
    dealership_id: int,
    message_id: int,
    attachment_id: str,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> Response:
    content, mime_type, filename = gmail_service.download_attachment(
        db,
        dealership_id,
        message_id,
        attachment_id,
    )
    safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip() or "attachment"
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(safe_filename, safe='')}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(
    "/dealerships/{dealership_id}/email-mailbox",
    status_code=status.HTTP_204_NO_CONTENT,
)
def disconnect_mailbox(
    dealership_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    gmail_service.disconnect_mailbox(db, dealership_id)


@router.get("/email/google/callback")
def google_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error or not code or not state:
        return RedirectResponse(
            gmail_service.frontend_redirect("/settings", gmail_error="connection"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        gmail_service.complete_authorization(db, code, state)
    except ApplicationError as exc:
        logger.info("Google mailbox authorization did not complete: %s", exc.error_code)
        return RedirectResponse(
            gmail_service.frontend_redirect("/settings", gmail_error="connection"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        gmail_service.frontend_redirect("/inbox", gmail_connected="1"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
