# Getting Started

This guide sets up the DealerDesk backend locally, seeds demo accounts, and verifies the API.

## Prerequisites

- Python 3.11+ (the code uses `X | None` type unions and `zoneinfo`)
- PostgreSQL 13+
- Git
- PowerShell (examples below) or an equivalent shell

## 1. Clone and enter the backend

```powershell
git clone <repository-url>
cd DealerDesk\backend
```

## 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Create the database

Create a PostgreSQL database (and role) for the application:

```sql
CREATE ROLE dealerdesk WITH LOGIN PASSWORD 'change-me';
CREATE DATABASE dealerdesk OWNER dealerdesk;
```

## 4. Configure the environment

```powershell
Copy-Item .env.example .env
```

Edit `backend/.env` and set at minimum:

```dotenv
DATABASE_URL=postgresql+psycopg://dealerdesk:change-me@localhost:5432/dealerdesk
JWT_SECRET_KEY=replace-with-a-long-random-secret
```

Optional integrations:

```dotenv
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_BUCKET_ID=brand-logos

RESEND_API_KEY=
```

See [Configuration](configuration.md) for all variables.

## 5. Start the API

```powershell
uvicorn app.main:app --reload
```

On startup the application:

1. Creates missing tables.
2. Runs the idempotent vehicle/brand migration.

Useful URLs:

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/` | Status message |
| `http://127.0.0.1:8000/api/v1/health` | Health check |
| `http://127.0.0.1:8000/docs` | Swagger UI |
| `http://127.0.0.1:8000/redoc` | ReDoc |

## 6. Seed demo accounts

The seed command is idempotent and refreshes passwords for existing demo accounts.

```powershell
python -m seed.seed_demo_user
```

| Account | Email | Password |
| --- | --- | --- |
| Customer | `customer-demo@dealerdesk.dev` | `DealerDeskCustomer!2026` |
| Dealership admin | `dealership-demo@dealerdesk.dev` | `DealerDeskDealership!2026` |

The dealership seed includes a `Toyota` brand and default test-drive settings. Do not use these credentials in production.

## 7. Verify with the API

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/auth/login `
  -ContentType application/json `
  -Body '{"email":"dealership-demo@dealerdesk.dev","password":"DealerDeskDealership!2026"}'

Invoke-RestMethod -Method Get `
  -Uri http://127.0.0.1:8000/api/v1/auth/me `
  -Headers @{ Authorization = "Bearer $($login.access_token)" }
```

Or use `curl`:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

## 8. A minimal end-to-end flow

1. Log in as the dealership admin.
2. `GET /api/v1/dealerships/{dealership_id}/brands` to obtain a `brand_id`.
3. `POST /api/v1/dealerships/{dealership_id}/vehicles` with `test_drive_enabled: true`.
4. `PUT /api/v1/dealerships/{dealership_id}/test-drive-settings` to choose hours/days.
5. `POST /api/v1/dealerships/{dealership_id}/test-drive-slots/generate?start_date=...&end_date=...`.
6. Log in as the customer and `POST /api/v1/dealerships/{dealership_id}/test-drive-slots/{slot_id}/bookings`.

Full contracts are in the [API Reference](api-reference.md).

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `database_url must contain a PostgreSQL URL` | `DATABASE_URL` is missing or not a PostgreSQL DSN. |
| `503` on login | `JWT_SECRET_KEY` is not configured. |
| `503` on logo upload | Supabase URL/key not configured, or bucket missing. |
| Emails not sent | `RESEND_API_KEY` is unset; responses show `email_provider_pending`. |
| Tests fail connecting | PostgreSQL is unreachable or `TEST_DATABASE_URL`/`DATABASE_URL` is wrong. |
| `ModuleNotFoundError: app` | Run commands from the `backend/` directory (tests set `pythonpath = .`). |

## Next steps

- [Testing](testing.md) — run and understand the suite.
- [Development Guide](development.md) — conventions and adding features.
- [Deployment](deployment.md) — production notes.
