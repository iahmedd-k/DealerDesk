from datetime import datetime, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError, UnauthorizedError
from app.db.session import get_db
from app.models.user import User
from app.repositories import auth_repository
from app.services import auth_service


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        user_id, token_version = auth_service.get_access_token_identity(token)
    except (ValueError, TypeError, jwt.InvalidTokenError):
        raise UnauthorizedError(
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except RuntimeError as exc:
        raise ServiceUnavailableError(str(exc)) from exc

    now = datetime.now(timezone.utc)
    revoked = auth_repository.has_revoked_access_token(
        db, auth_service.hash_token(token), now
    )
    if revoked:
        raise UnauthorizedError("Token revoked")
    current_version = auth_repository.get_token_version(db, user_id)
    if token_version != current_version:
        raise UnauthorizedError("Token revoked")
    user = auth_repository.get_active_user(db, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return user
