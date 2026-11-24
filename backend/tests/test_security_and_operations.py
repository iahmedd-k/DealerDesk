from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.idempotency import IdempotencyKey
from app.models.user import EmailVerificationToken, User
from app.services import account_service
from app.services.retention_service import cleanup_expired_data


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


def test_distributed_idempotency_database_persistence(test_client: TestClient) -> None:
    key = "idem-distrib-unit-test-101"
    db = SessionLocal()
    try:
        # Clear any preexisting key with this test identifier
        db.query(IdempotencyKey).filter(IdempotencyKey.scope_key.like("%" + key + "%")).delete(
            synchronize_session=False
        )
        db.commit()

        with patch("app.services.account_service.login") as mock_login:
            from app.schemas.auth import TokenResponse

            mock_login.return_value = TokenResponse(
                access_token="mock-dist-token",
                refresh_token="mock-dist-refresh",
                token_type="bearer",
                expires_in=1800,
            )

            # First request: should execute and persist record
            res1 = test_client.post(
                "/api/v1/auth/login",
                headers={"Idempotency-Key": key},
                json={"email": "dealerdesk@demo.com", "password": "adminadmin"},
            )
            assert res1.status_code == 200
            assert "Idempotent-Replayed" not in res1.headers
            assert mock_login.call_count == 1

            # Second request with same payload: must replay from database without executing login
            res2 = test_client.post(
                "/api/v1/auth/login",
                headers={"Idempotency-Key": key},
                json={"email": "dealerdesk@demo.com", "password": "adminadmin"},
            )
            assert res2.status_code == 200
            assert res2.headers.get("Idempotent-Replayed") == "true"
            assert res2.json() == res1.json()
            assert mock_login.call_count == 1

            # Third request with different payload: must return 409 Conflict
            res3 = test_client.post(
                "/api/v1/auth/login",
                headers={"Idempotency-Key": key},
                json={"email": "diff@demo.com", "password": "adminadmin"},
            )
            assert res3.status_code == 409
            assert mock_login.call_count == 1
    finally:
        db.close()


def test_cookie_based_authentication(test_client: TestClient) -> None:
    with patch("app.services.account_service.login") as mock_login:
        from app.schemas.auth import TokenResponse

        mock_login.return_value = TokenResponse(
            access_token="test-cookie-jwt-access",
            refresh_token="test-cookie-jwt-refresh-32charslongminimum",
            token_type="bearer",
            expires_in=1800,
        )

        res = test_client.post(
            "/api/v1/auth/login",
            json={"email": "dealerdesk@demo.com", "password": "adminadmin"},
        )
        assert res.status_code == 200
        # Verify HttpOnly cookies are set
        assert "dd_access" in res.cookies
        assert "dd_refresh" in res.cookies
        assert res.cookies["dd_access"] == "test-cookie-jwt-access"

    # Verify cookie-authenticated request to /auth/me
    with patch("app.dependencies.auth.auth_service.get_access_token_identity") as mock_identity, \
         patch("app.dependencies.auth.auth_repository.has_revoked_access_token", return_value=False), \
         patch("app.dependencies.auth.auth_repository.get_token_version", return_value=1), \
         patch("app.dependencies.auth.auth_repository.get_active_user") as mock_user:

        mock_identity.return_value = (1, 1)
        mock_user.return_value = User(
            id=1,
            name="Demo Admin",
            email="dealerdesk@demo.com",
            role="dealerdesk_admin",
            is_active=True,
            dealership_id=None,
            must_change_password=False,
        )

        # Call with cookie, omitting Authorization header completely
        me_res = test_client.get(
            "/api/v1/auth/me",
            headers={"Cookie": "dd_access=test-cookie-jwt-access"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "dealerdesk@demo.com"

        # Logout clears cookies
        with patch("app.services.account_service.logout"):
            logout_res = test_client.post(
                "/api/v1/auth/logout",
                headers={"Cookie": "dd_access=test-cookie-jwt-access"},
            )
            assert logout_res.status_code == 204
            # Cookie header should set deleted/expired
            set_cookie_headers = logout_res.headers.get("set-cookie", "")
            assert "dd_access" in set_cookie_headers


def test_account_lockout_after_failed_attempts() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "lockout_test@demo.com").first()
        if not user:
            from app.services import auth_service
            user = User(
                name="Lockout Target",
                email="lockout_test@demo.com",
                password=auth_service.hash_password("RealPassword123!"),
                role="customer",
                is_active=True,
                failed_login_attempts=0,
                locked_until=None,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 4 failed attempts should not lock
        from app.schemas.auth import LoginRequest
        bad_req = LoginRequest(email="lockout_test@demo.com", password="WrongPassword!")

        for _ in range(4):
            with pytest.raises(Exception):
                account_service.login(db, bad_req)

        db.refresh(user)
        assert user.failed_login_attempts == 4
        assert user.locked_until is None

        # 5th failed attempt should trigger lockout
        with pytest.raises(Exception):
            account_service.login(db, bad_req)

        db.refresh(user)
        assert user.failed_login_attempts == 5
        assert user.locked_until is not None
        assert user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)

        # Subsequent login attempts must be rejected with lockout message
        with pytest.raises(Exception) as exc_info:
            account_service.login(db, bad_req)
        assert "temporarily locked" in str(exc_info.value).lower()

        # Reset user
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    finally:
        db.close()


def test_email_verification_flow() -> None:
    db = SessionLocal()
    try:
        from app.services import auth_service
        email = "verify_test@demo.com"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                name="Verify Target",
                email=email,
                password=auth_service.hash_password("Pass!12345"),
                role="customer",
                is_active=True,
                is_email_verified=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.is_email_verified = False
            db.commit()

        raw_token = "verify-token-super-secret-unique-string-12345"
        token_entry = EmailVerificationToken(
            user_id=user.id,
            token_hash=auth_service.hash_token(raw_token),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(token_entry)
        db.commit()

        # Verify email using service
        result = account_service.verify_email(db, raw_token)
        assert "verified successfully" in result["message"]

        db.refresh(user)
        assert user.is_email_verified is True
        db.refresh(token_entry)
        assert token_entry.used_at is not None
    finally:
        db.close()


def test_data_retention_service() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Seed an expired idempotency key and old audit log
        expired_key = IdempotencyKey(
            scope_key="test-expired-key-for-retention-999",
            request_hash="hash",
            status="completed",
            created_at=now - timedelta(days=2),
            locked_until=now - timedelta(days=2),
            expires_at=now - timedelta(hours=1),
        )
        db.add(expired_key)

        old_audit = AuditLog(
            action="test.old_action",
            resource_type="system",
            created_at=now - timedelta(days=400),
        )
        db.add(old_audit)
        db.commit()

        # Run retention cleanup
        report = cleanup_expired_data(db, dry_run=False, audit_retention_days=365)
        assert report["dry_run"] is False
        assert report["cleaned_counts"]["idempotency_keys"] >= 1
        assert report["cleaned_counts"]["audit_logs"] >= 1
    finally:
        db.close()


def test_deep_health_check_diagnostics(test_client: TestClient) -> None:
    res = test_client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert "latency_ms" in data["database"]
    assert "pool" in data["database"]
    assert "environment" in data
    assert "services" in data


@pytest.mark.no_db
def test_production_config_validation() -> None:
    with pytest.raises(ValueError, match="In production, JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SUPABASE_CONNECTION_STRING="postgresql://postgres:secret@localhost:5432/postgres",
            jwt_secret_key="short",
        )

    with pytest.raises(ValueError, match="known default test key"):
        Settings(
            ENVIRONMENT="production",
            SUPABASE_CONNECTION_STRING="postgresql://postgres:secret@localhost:5432/postgres",
            jwt_secret_key="test-only-jwt-secret-that-is-at-least-32-bytes",
        )
