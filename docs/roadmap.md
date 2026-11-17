# Roadmap and Limitations

This document separates what is implemented from what is planned or missing, and records known risks discovered while analysing the current codebase.

## Implemented

- JWT authentication with rotating refresh tokens, logout revocation, and global token invalidation.
- Customer self-registration and profile management.
- Password reset and staff invitation activation flows.
- Dealership registration (dealership + brands + admin + settings in one transaction).
- Dealership profile updates and soft deactivation.
- Brand CRUD with case-insensitive uniqueness, 20-brand limit, archive/restore, and logo upload.
- Vehicle inventory with brand validation, availability toggle, and soft deletion.
- Staff invitations, role management, revocation, and last-admin protection.
- Test-drive settings, timezone/DST-aware slot generation, reconciliation, and per-slot capacity.
- Customer booking/cancellation with duplicate and capacity protection.
- Role-based and dealership-scoped authorization.
- Optional Resend email and Supabase Storage integrations.
- Startup schema provisioning and legacy vehicle/brand backfill.
- Integration and unit test suite against PostgreSQL.
- Idempotent demo seeding.

## Not implemented (observed gaps)

### Frontend
- `frontend/` contains only `node_modules`; there is no application source, framework config, or UI.
- No TypeScript components, API client layer, or state management.

### Migration management
- No Alembic revisions or `alembic.ini` workflow are present, despite `alembic` being listed in `requirements.txt`.
- Schema changes rely on `create_all` and hand-written idempotent SQL in `app/db/migrations.py`, executed at startup.
- No downgrade path or migration history.

### API platform features
- No pagination, filtering, or sorting on collection endpoints.
- No standard response envelope or error codes beyond `detail`.
- No API versioning beyond the `/api/v1` prefix.
- No OpenAPI examples on most endpoints (auth schemas have some).
- No idempotency keys for retried writes.

### Security and operations
- No CORS configuration; browser clients on other origins are blocked.
- No rate limiting, brute-force protection, or account lockout.
- No email verification.
- Refresh tokens, password-reset tokens, and invitation tokens are stored in plaintext.
- No audit log.
- No structured request logging or correlation IDs.
- `/api/v1/health` does not check database or external dependencies.
- No container image, CI pipeline, or infrastructure-as-code in the repository.

### Domain features
- No vehicle image management or media pipeline (only brand logos).
- No sales leads, deals, or customer CRM beyond accounts.
- No staff availability or per-salesperson scheduling.
- No notifications/reminders for bookings.
- No support for multiple locations per dealership.
- No reporting or analytics endpoints.
- No pagination for staff, users, or bookings.

### Code quality
- Repository pattern is only partially applied; several endpoints contain direct ORM queries.
- Some domain logic (e.g., slot reconciliation, brand lifecycle) lives in endpoint modules rather than services.
- `price` uses a floating-point column instead of a fixed-precision decimal.
- `print` is used for the startup banner instead of structured logging (despite the repository rule).
- Duplicated access-check helpers (`_ensure_dealership_access`, `_get_active_dealership`) exist in multiple endpoint modules and could be centralized.

## Suggested next steps

Prioritized by impact and risk:

1. **Add CORS and rate limiting** before any browser frontend or public exposure.
2. **Adopt a real migration workflow** (Alembic) for reviewable, reversible schema changes.
3. **Harden token storage** — hash refresh/reset/invitation tokens at rest.
4. **Add pagination and filtering** to collection endpoints.
5. **Extract remaining SQL into repositories/services** to match the stated architecture.
6. **Switch monetary values to `Numeric`/`Decimal`**.
7. **Add health checks** for database and external services.
8. **Add audit logging and request tracing**.
9. **Build the frontend** on top of the documented API.
10. **Add CI** running Ruff and the PostgreSQL-backed test suite.

## Risk register

| Risk | Severity | Notes | Mitigation |
| --- | --- | --- | --- |
| Plaintext refresh/reset/invitation tokens | High | DB compromise exposes active sessions | Hash tokens at rest; compare hashes |
| No rate limiting on auth | High | Credential stuffing / brute force | Edge rate limits; login throttling |
| No CORS | Medium | Blocks browser clients; teams may disable protections ad hoc | Add `CORSMiddleware` with explicit origins |
| Startup DDL under app role | Medium | Runtime role needs schema-alter rights; concurrent starts | Use a migration job and least-privilege runtime role |
| Floating-point money | Medium | Rounding errors | Use `Numeric(12, 2)` |
| Inline ORM in endpoints | Low/Medium | Harder to test and evolve | Extract repositories/services |
| No pagination | Medium | Large collections heavy on DB/app | Add paginated list endpoints |
| Email optional by default | Low | Invites/resets silently not delivered when unconfigured | Document, monitor `delivery_status` |
| Health endpoint shallow | Low | Orchestrators cannot detect DB outages | Add dependency probes |

## Related documents

- [Overview](overview.md)
- [Architecture](architecture.md)
- [Deployment](deployment.md)
- [Development Guide](development.md)
