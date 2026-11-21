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

The application does not create or alter tables at runtime. Apply the Alembic
revision chain before starting the API:

```bash
cd backend
alembic upgrade head
```

The Docker Compose stack runs this as a one-shot `migrate` service and starts
the backend only after the migration succeeds. For other deployment platforms,
run the same command as a release step using a migration-capable database role;
the application runtime role should not need schema-alter privileges. The
backend disposes its SQLAlchemy engine on shutdown.

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
| `VEHICLE_IMAGES_BUCKET_ID` | Vehicle image bucket (default `vehicle-images`) |
| `RESEND_API_KEY` | Invitation and reset emails |
| `RESEND_FROM_EMAIL` | Verified sender |
| `DATABASE_POOL_*` | Pool tuning for your database plan |

See [Configuration](configuration.md).

## External service setup

### Supabase Storage

1. Create public buckets for brand logos (`brand-logos`) and vehicle images
   (`vehicle-images`), or configure the bucket names below.
2. Set `SUPABASE_URL` and `SUPABASE_KEY`.
3. Ensure the server key can write to the bucket.
4. Logos and vehicle images are stored under dealership-scoped object paths.

If unconfigured, logo endpoints return `503`; the rest of the API works.

### Resend

1. Verify a sending domain in Resend.
2. Set `RESEND_API_KEY` and `RESEND_FROM_EMAIL`.
3. Optionally set `RESEND_REPLY_TO`.

If unconfigured, invitations and reset requests still persist records but email status is `email_provider_pending`, and password-reset tokens are removed so they cannot be consumed.

## Production checklist

- [ ] Use a strong random `JWT_SECRET_KEY` (32+ bytes) from a secret manager.
- [ ] Use a TLS-enabled PostgreSQL DSN and a least-privilege application role.
- [ ] Run `alembic upgrade head` as a release step before deploying new code.
- [ ] Set `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` appropriate to the database plan.
- [ ] Configure Supabase and Resend if those features are required.
- [ ] Run with multiple workers behind a reverse proxy that terminates TLS.
- [ ] Restrict database network access to the application.
- [ ] Back up the database and test restore procedures.
- [ ] Ensure logs are captured centrally; do not log secrets or tokens.
- [ ] Configure assistant/authentication rate limits and edge protections for public traffic.
- [ ] Set explicit CORS origins for the deployed frontend.
- [ ] Monitor error rates on auth, booking, and migration startup.

## Known deployment constraints

| Constraint | Impact |
| --- | --- |
| Assistant replies depend on configured catalog and knowledge data | Missing source data is reported as unavailable; it is not inferred. |
| Health check | `/api/v1/health` probes PostgreSQL; external service statuses report configuration, not live connectivity. |

## Scaling notes

- The app is stateless for access tokens (JWT), but revocation and refresh state live in PostgreSQL, so all instances share the same database.
- Row-level locks (`SELECT ... FOR UPDATE`) serialize booking/cancellation, customer overlap checks, and last-admin checks. Keep transactions short under load.
- Brand logo storage is offloaded to Supabase; the app only proxies uploads.

## Related documents

- [Architecture](architecture.md)
- [Configuration](configuration.md)
- [Roadmap & Limitations](roadmap.md)
