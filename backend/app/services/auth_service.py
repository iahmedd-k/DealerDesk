from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings


password_hash = PasswordHash.recommended()
revoked_tokens: set[str] = set()


def _get_jwt_secret() -> str:
    secret = get_settings().jwt_secret_key
    if secret is None or not secret.get_secret_value():
        raise RuntimeError("JWT_SECRET_KEY must be configured in the environment")
    return secret.get_secret_value()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        _get_jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def revoke_token(token: str) -> None:
    revoked_tokens.add(token)


def is_token_revoked(token: str) -> bool:
    return token in revoked_tokens


def get_user_id_from_token(token: str) -> int:
    settings = get_settings()
    payload = jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=[settings.jwt_algorithm],
    )
    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token does not contain a user")
    return int(subject)