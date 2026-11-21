# Deployment

This document covers runtime behaviour and production considerations for the DealerDesk backend.

## Runtime model

- Single FastAPI ASGI application (`app.main:app`).
- Deploy behind an ASGI server such as Uvicorn or Gunicorn with Uvicorn workers, or a platform that serves ASGI apps.
- Requires a reachable PostgreSQL database.
- Optional dependencies: Supabase Storage (brand logos) and Resend (email).

Example production-style command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Run from the `backend/` directory so imports resolve. Some platforms prefer a module path with `--app-dir backend`.

## Startup behaviour

On startup the application:

1. Connects to PostgreSQL using `DATABASE_URL` (or its aliases).
2. Runs `Base.metadata.create_all` to create missing tables.
3. Runs `ensure_vehicle_brand_associations`:
   - Adds `vehicles.brand_id` and its index if missing.
   - Creates brands from legacy `make` values and backfills associations.
   - Adds the brand foreign key and sets `brand_id NOT NULL`.
   - **Fails startup** if any vehicle cannot be associated.
4. Creates the partial unique index for active test-drive bookings.
5. On shutdown, disposes the engine.

Implications:

- The first startup needs DDL privileges on the database.
- Multiple workers may run startup concurrently; operations are written to be idempotent, but a migration-capable role is advisable.
- There is **no Alembic revision history** in the repo despite `alembic` being installed. Schema evolution currently relies on `create_all` and the startup migration. See [Roadmap & Limitations](roadmap.md).

## Required configuration

Minimum:

| Variable | Why |
| --- | --- |
| `DATABASE_URL` | Database connectivity |
| `JWT_SECRET_KEY` | Token issuing/validation |

Recommended for full functionality:

| Variable | Enables |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_KEY` | Brand logo upload/delete |
| `SUPABASE_BUCKET_ID` | Target bucket (default `brand-logos`) |
| `RESEND_API_KEY` | Invitation and reset emails |
| `RESEND_FROM_EMAIL` | Verified sender |
| `DATABASE_POOL_*` | Pool tuning for your database plan |

See [Configuration](configuration.md).

## External service setup

### Supabase Storage

1. Create a **public** bucket (default name `brand-logos`).
2. Set `SUPABASE_URL` and `SUPABASE_KEY`.
3. Ensure the server key can write to the bucket.
4. Logos are stored at `dealerships/{dealership_id}/brands/{brand_id}/logo` with upsert enabled.

If unconfigured, logo endpoints return `503`; the rest of the API works.

### Resend

1. Verify a sending domain in Resend.
2. Set `RESEND_API_KEY` and `RESEND_FROM_EMAIL`.
3. Optionally set `RESEND_REPLY_TO`.

If unconfigured, invitations and reset requests still persist records but email status is `email_provider_pending`, and password-reset tokens are removed so they cannot be consumed.

## Production checklist

- [ ] Use a strong random `JWT_SECRET_KEY` (32+ bytes) from a secret manager.
- [ ] Use a TLS-enabled PostgreSQL DSN and a least-privilege application role.
- [ ] Set `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` appropriate to the database plan.
- [ ] Configure Supabase and Resend if those features are required.
- [ ] Run with multiple workers behind a reverse proxy that terminates TLS.
- [ ] Restrict database network access to the application.
- [ ] Back up the database and test restore procedures.
- [ ] Ensure logs are captured centrally; do not log secrets or tokens.
- [ ] Add rate limiting / WAF at the edge until in-app controls exist.
- [ ] Configure CORS at the edge or add middleware before serving a browser frontend.
- [ ] Monitor error rates on auth, booking, and migration startup.

## Known deployment constraints

| Constraint | Impact |
| --- | --- |
| Refresh/reset/invitation tokens stored plaintext | Database read access exposes session/reset secrets. |
| Startup DDL | Requires schema-alter privileges at runtime. |
| Health check | `/api/v1/health` probes PostgreSQL; external service statuses report configuration, not live connectivity. |

## Scaling notes

- The app is stateless for access tokens (JWT), but revocation and refresh state live in PostgreSQL, so all instances share the same database.
- Row-level locks (`SELECT ... FOR UPDATE`) serialize booking/cancellation and last-admin checks. Keep transactions short under load.
- Brand logo storage is offloaded to Supabase; the app only proxies uploads.

## Related documents

- [Architecture](architecture.md)
- [Configuration](configuration.md)
- [Roadmap & Limitations](roadmap.md)
