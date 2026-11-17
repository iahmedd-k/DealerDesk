import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories import auth_repository


password_hash = PasswordHash.recommended()


def _get_jwt_secret() -> str:
    secret = get_settings().jwt_secret_key
    if secret is None or not secret.get_secret_value():
        raise RuntimeError("JWT_SECRET_KEY must be configured in the environment")
    return secret.get_secret_value()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int, token_version: int = 0) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at, "ver": token_version},
        _get_jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_access_token_expiry(token: str) -> datetime:
    settings = get_settings()
    payload = jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=[settings.jwt_algorithm],
    )
    expires_at = payload.get("exp")
    if not isinstance(expires_at, (int, float)):
        raise ValueError("Token does not contain an expiration")
    return datetime.fromtimestamp(expires_at, timezone.utc)


def revoke_user_refresh_tokens(db: Session, user_id: int) -> None:
    auth_repository.revoke_refresh_tokens(db, user_id, datetime.now(timezone.utc))


def get_user_token_version(db: Session, user_id: int) -> int:
    return auth_repository.get_token_version(db, user_id)


def invalidate_user_access_tokens(db: Session, user_id: int) -> None:
    auth_repository.increment_token_version(db, user_id)


def get_user_id_from_token(token: str) -> int:
    return get_access_token_identity(token)[0]


def get_access_token_identity(token: str) -> tuple[int, int]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=[settings.jwt_algorithm],
    )
    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token does not contain a user")
    version = payload.get("ver", 0)
    if not isinstance(version, int) or version < 0:
        raise ValueError("Token contains an invalid version")
    return int(subject), version
