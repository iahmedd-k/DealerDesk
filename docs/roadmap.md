# Roadmap and Limitations

This document separates what is implemented from what is planned or missing, and records known risks discovered while analysing the current codebase.

## Implemented

- JWT authentication with rotating refresh tokens, logout revocation, and global token invalidation.
- Platform superadmin role (`dealerdesk_admin`) with cross-dealership management, user listing, and tenant oversight.
- Customer self-registration and profile management.
- Password reset and staff invitation activation flows.
- Dealership registration (dealership + brands + admin + settings in one transaction).
- Dealership profile updates and soft deactivation.
- Brand CRUD with case-insensitive uniqueness, 20-brand limit, archive/restore, and logo upload.
- Vehicle inventory with brand validation, availability toggle, and soft deletion.
- Multi-image vehicle media management backed by Supabase Storage, including validation, display ordering, alt text, and deletion.
- Staff invitations, role management, revocation, and last-admin protection.
- Test-drive settings, timezone/DST-aware slot generation, reconciliation, and per-slot capacity.
- Test-drive availability queries with `available_only`, `vehicle_id`, and date range filters, with real-time `remaining_capacity` and `is_available` computed fields (FR-016).
- Customer test-drive booking with explicit confirmation, row-level locks, atomic capacity decrement, and duplicate/overlap prevention (FR-017).
- Booking management (FR-018): Staff can view all dealership bookings, reschedule, and cancel; customer-facing rescheduling and cancellation enforces contact and identity verification.
- CORS middleware with configurable allowed origins (`CORS_ORIGINS`).
- Role-based and dealership-scoped authorization across all CRUD endpoints.
- Optional Resend email and Supabase Storage integrations.
- Startup schema provisioning and legacy vehicle/brand backfill.
- Integration and unit test suite against PostgreSQL.
- Idempotent demo seeding for all roles (`dealerdesk@demo.com`, `dealership@demo.com`, `customer@demo.com`).
- Alembic database migration management with versioned revisions, `alembic.ini`, schema downgrade support, and programmatic startup upgrades.
- Dealership knowledge document ingestion for PDF, TXT, and Markdown, with optional brand scoping.
- Chunk indexing, configurable embeddings, source-aware retrieval, and document deletion.
- Dealership-grounded AI Assistant (`POST /api/v1/dealerships/{dealership_id}/assistant/chat`) with intent detection, live inventory grounding, test-drive slot lookup, RAG semantic knowledge chunk retrieval, and remote OpenAI provider with fallback local heuristic engine.
- Pagination, filtering, and sorting across collection endpoints with standard `X-Total-Count`, `X-Page`, `X-Page-Size`, and `X-Total-Pages` response headers.
- Standard structured error envelope (`detail`, `error_code`, `request_id`, `timestamp`) across all API errors.
- Idempotency middleware caching 200/201 responses with 24-hour TTL and `Idempotent-Replayed: true` header for retry-safe writes.
- Structured request logging and correlation ID propagation (`X-Request-ID` header and context).
- Deep operational health check (`/api/v1/health`) probing PostgreSQL connectivity, query latency, and external service dependency status.
- Audit logging system tracking actor, dealership, action, resource, timestamp, and client IP (`audit_logs` table & API).
- Configurable rate limiting on auth endpoints via `slowapi` (`AUTH_RATE_LIMIT`).
- Multi-stage production `backend/Dockerfile`, `docker-compose.yml`, and GitHub Actions CI workflow (`.github/workflows/ci.yml`).
- Next.js 15 frontend foundation initialized in `frontend/`.

## Not implemented (observed gaps)

### Frontend
- Next.js application foundation configured; UI pages, components, and dashboard interfaces are under development.
- Needs complete API client layer and state management.

### Security and operations
- Email verification flow (tokens currently expire and verify upon redemption).
- Account lockout after consecutive failed attempts.

### Domain features
- No sales leads, deals, or customer CRM beyond accounts.
- No staff availability or per-salesperson scheduling.
- No notifications/reminders for bookings.
- No support for multiple locations per dealership.
- No reporting or analytics endpoints.
- No OCR for scanned/rasterized PDFs in knowledge ingestion.

### Code quality
- Vehicle prices use fixed-precision storage; health database checks use repository/service layers.
- Startup status uses structured logging, and repeated dealership/role access checks use shared helpers.
- Slot reconciliation and brand lifecycle logic live in domain services.

## Suggested next steps

Prioritized by impact and risk:

1. **Harden token storage** — hash refresh/reset/invitation tokens at rest.
2. **Extract remaining SQL into repositories/services** to match the stated architecture.
3. **Add audit logging and request tracing**.
4. **Build out the frontend** on top of the documented API.
5. **Add CI** running Ruff and the PostgreSQL-backed test suite.

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
