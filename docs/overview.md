# Overview

DealerDesk is a backend service for managing vehicle dealerships and their customer-facing test-drive experience. It exposes a versioned REST API under `/api/v1` and is built with FastAPI and PostgreSQL.

## Goals

- Let a dealership register a workspace, define its brands, and manage inventory.
- Let dealership staff collaborate through roles and invitations.
- Let customers browse a dealership's inventory and book test drives.
- Enforce dealership isolation, role permissions, and data integrity server-side.
- Keep historical records intact when brands or vehicles are retired (soft deletion).

## Personas and roles

| Role | Scope | Description |
| --- | --- | --- |
| `customer` | No dealership | Public account. Can book and cancel their own test drives. |
| `dealership_admin` | One dealership | Full workspace control: dealership settings, staff, brands, vehicles, scheduling. |
| `manager` | One dealership | Manages brands and inventory; can view staff; cannot change dealership-level settings or manage staff roles. |
| `sales_rep` | One dealership | Manages vehicle availability and details. |

Roles are stored on the `users` table and enforced on every protected route. See [Authentication](authentication.md).

## Implemented capabilities

### Accounts and sessions
- Customer self-registration (`/auth/signup`).
- Email/password login issuing an access token and a rotating refresh token.
- Logout with access-token revocation and refresh-token revocation.
- Profile read/update and account deletion (soft deactivation).
- Password change, password reset (request + confirm), and staff invitation activation.
- Password hashing with Argon2 (via `pwdlib`).

### Dealerships
- Public dealership registration that atomically creates the dealership, its initial brands, its admin user, and default test-drive settings.
- Public listing and retrieval of active dealerships.
- Admin-only update of dealership profile and timezone.
- Admin-only soft deactivation of a dealership.

### Brands
- Initial 1–20 brands created at registration.
- Case-insensitive uniqueness per dealership (among non-deleted brands).
- Hard limit of 20 non-deleted brands per dealership.
- Rename, activate/deactivate, soft-delete (archive), and restore.
- Optional JPEG/PNG/WebP logo upload (max 3 MB) backed by Supabase Storage.
- Deactivating or deleting a brand deactivates its future test-drive slots and hides its vehicles from default inventory listings while preserving history.

### Vehicles
- Create/read/update inventory per dealership, always associated with an active brand in the same dealership.
- Unique stock number per dealership.
- Availability toggle and soft deletion (marks unavailable and disables test drives).
- Archived-brand vehicles remain retrievable individually but are excluded from default listings.

### Staff
- Admin-only invitations for `manager` and `sales_rep` roles with expiring activation tokens.
- Invitations can be re-sent, revoked, and activated.
- Staff listing/read for admins and managers; role changes and removal for admins.
- Guard rails prevent removing, demoting, or deactivating the last active dealership admin.

### Test drives
- Per-dealership settings: opening/closing time, slot duration, capacity, open weekdays.
- Timezone-aware slot generation for available, test-drive-enabled vehicles.
- Slot listing, inspection, activation/deactivation, and deactivation-on-delete.
- Customer booking with capacity, availability, duplicate-booking, and past-slot checks.
- Customer cancellation and staff-side cancellation.
- Automatic reconciliation of future slots when settings change.

### Platform
- Health and status endpoints.
- Optional Resend email delivery for password resets and staff invitations.
- Idempotent startup migration that backfills vehicle-to-brand associations.
- Pytest integration suite against a dedicated PostgreSQL schema.
- Demo seeding for local and integration testing.

## Current status

| Area | Status |
| --- | --- |
| Backend API | Implemented |
| Database models and startup migration | Implemented |
| Authentication and authorization | Implemented |
| Test suite | Implemented (integration + unit) |
| Email delivery | Implemented, optional (requires Resend key) |
| Brand logo storage | Implemented, optional (requires Supabase config) |
| Alembic migration history | Not used; schema is created at startup (see [Deployment](deployment.md)) |
| Frontend | Not implemented (`frontend/` only contains `node_modules`) |
| CORS, rate limiting, pagination | Not implemented (see [Roadmap](roadmap.md)) |

## Related documents

- [Architecture](architecture.md) for how the pieces fit together.
- [API Reference](api-reference.md) for the endpoint contract.
- [Roadmap & Limitations](roadmap.md) for planned work and risks.
