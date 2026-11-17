# Testing

DealerDesk uses `pytest` with FastAPI's `TestClient` for integration tests and direct unit tests for pure logic. Tests run against a **real PostgreSQL database** in a dedicated schema.

## Test database

- The suite uses `TEST_DATABASE_URL` when set, otherwise `Settings().database_url`.
- It always targets the schema `dealerdesk_test`.
- The schema is dropped and recreated **before and after every test** (`reset_database` autouse fixture). Do not store application data in this schema.
- The suite sets these environment values at import time:
  - `SUPABASE_CONNECTION_STRING` and `DATABASE_URL` to the test DSN
  - `DATABASE_SCHEMA=dealerdesk_test`
  - `JWT_SECRET_KEY=test-only-jwt-secret-that-is-at-least-32-bytes`
  - `RESEND_API_KEY=""` (email disabled)

## Running tests

From `backend/`:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/dealerdesk_test"
pytest
```

Run a single file or test:

```powershell
pytest tests/test_brands_api.py
pytest tests/test_endpoint_coverage.py -q
```

Configuration lives in `backend/pytest.ini` (`pythonpath = .`, `asyncio_default_fixture_loop_scope = function`).

## Fixtures (`tests/conftest.py`)

| Fixture | Scope | Purpose |
| --- | --- | --- |
| `reset_database` | function, autouse | Drops/recreates `dealerdesk_test` and creates tables. |
| `db` | function | Yields a `Session`, closed afterward. |
| `client` | function | Yields a `TestClient` with the app lifespan (startup migration runs). |
| `seeded_users` | function | Runs `seed_demo_users()` and returns `(customer, dealership_admin)`. |

## Test suites

| File | Focus |
| --- | --- |
| `test_auth_service.py` | Password hashing, JWT claims/expiry, token hashing, missing-secret handling. |
| `test_auth_api.py` | Login, logout revocation, signup, change-password. |
| `test_workspace_api.py` | Role enforcement on vehicle creation; admin vehicle/settings management. |
| `test_full_crud_api.py` | Auth profile/refresh/reset/delete, password-reset failure cleanup, dealership/staff/vehicle CRUD, settings/slot/booking flow. |
| `test_brands_api.py` | Brand validation and limit, legacy make backfill, brand lifecycle and history preservation, cross-dealership isolation, logo upload validation via mocked Supabase. |
| `test_testdrive_schedule.py` | DST-aware slot generation and timezone validation. |
| `test_endpoint_coverage.py` | Walks every route through realistic admin/customer workflows, including negative cases and dealership deactivation. |
| `test_seed_demo_users.py` | Seed idempotency and credential verification. |

## What is covered

- Authentication happy paths and failures (invalid password, revoked tokens, rotated refresh tokens).
- Authorization: customer vs. admin, cross-dealership access (`404`), last-admin guard (`409`).
- Brand limits, case-insensitive uniqueness, archive/restore semantics.
- Vehicle/brand consistency and stock-number uniqueness.
- Test-drive setting reconciliation, timezone/DST handling, slot capacity, duplicate booking prevention, cancellation and re-booking.
- Password-reset token cleanup when email delivery fails.
- Brand logo content-type, size, signature validation, and storage calls (mocked client).

## What is not covered yet

- Frontend (none implemented).
- Live Supabase or Resend integration (mocked/disabled).
- Load, concurrency, and security scanning.
- CORS and rate-limiting behaviour (not implemented).

## Conventions for new tests

- Put tests in `backend/tests/` and follow `test_<area>.py` naming.
- Use the existing `client`, `db`, and `seeded_users` fixtures.
- Mock external services (Supabase, Resend) with `monkeypatch`, as the existing suites do.
- Cover happy paths, edge cases, and failure responses.
- Never weaken or delete tests to make a run pass.

## Linting

```powershell
ruff check .
ruff format --check .
```

Use these before opening a change. See [Development Guide](development.md).

## Related documents

- [Getting Started](getting-started.md)
- [Configuration](configuration.md)
- [API Reference](api-reference.md)
