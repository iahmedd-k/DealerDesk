from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.services import auth_service


def test_password_hash_round_trip() -> None:
    password = "unit-test-password"
    hashed = auth_service.hash_password(password)

    assert hashed != password
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("wrong-password", hashed)


def test_access_token_contains_user_and_expiry() -> None:
    token = auth_service.create_access_token(42)

    payload = jwt.decode(token, "test-only-jwt-secret-that-is-at-least-32-bytes", algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert datetime.now(timezone.utc) < datetime.fromtimestamp(payload["exp"], timezone.utc) <= (
        datetime.now(timezone.utc) + timedelta(minutes=30)
    )


def test_revoked_token_is_rejected() -> None:
    token = "token-to-revoke"
    auth_service.revoke_token(token)

    assert auth_service.is_token_revoked(token)


def test_missing_jwt_secret_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be configured"):
        auth_service.create_access_token(1)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-jwt-secret-that-is-at-least-32-bytes")
    get_settings.cache_clear()
