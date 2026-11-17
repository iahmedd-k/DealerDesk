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
    token = auth_service.create_access_token(42, token_version=3)

    payload = jwt.decode(
        token, "test-only-jwt-secret-that-is-at-least-32-bytes", algorithms=["HS256"]
    )
    assert payload["sub"] == "42"
    assert payload["ver"] == 3
    assert auth_service.get_access_token_identity(token) == (42, 3)
    assert (
        datetime.now(timezone.utc)
        < datetime.fromtimestamp(payload["exp"], timezone.utc)
        <= (datetime.now(timezone.utc) + timedelta(minutes=30))
    )


def test_token_hash_is_stable_and_one_way() -> None:
    token = "access-token-value"
    assert auth_service.hash_token(token) == auth_service.hash_token(token)
    assert auth_service.hash_token(token) != token


def test_missing_jwt_secret_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be configured"):
        auth_service.create_access_token(1)
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-only-jwt-secret-that-is-at-least-32-bytes"
    )
    get_settings.cache_clear()
