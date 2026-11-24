# Roadmap and Limitations

This document distinguishes implemented workflows from the remaining product
and operational gaps. See the [functional requirements](functional-requirements.md)
for requirement-level status.

## Implemented

- JWT sign-in, customer registration, role and dealership authorization, rotating
  refresh tokens, logout revocation, password reset, and staff invitations.
- Refresh, reset, and invitation tokens are stored as SHA-256 digests.
- Dealership, brand, staff, inventory, and vehicle-media workflows, including
  Supabase Storage integration for vehicle images.
- Test-drive slot generation, local-time filtering, capacity-aware booking,
  rescheduling, cancellation, and customer/vehicle/schedule metadata in booking
  responses.
- Dealership-scoped knowledge ingestion and retrieval for supported PDF and
  text documents, with source metadata.
- Assistant responses use dealership inventory, slot, and eligible knowledge
  context; request validation, safety checks, output scrubbing, and rate
  limiting are applied.
- Persistent dealership lead capture with explicit contact consent, source and
  vehicle interest, staff assignment, status, follow-up time, and matching
  test-drive booking linkage. The assistant follow-up form creates a lead.
- Frontend pages call the backend APIs and report loading and request errors;
  customer and staff workflows are role-aware.
- Inventory lifecycle management supporting rich states (`available`, `reserved`, `sold`, `in_transit`, `unavailable`), audited status transitions (`VehicleStatusHistory`), audit log integration (`AuditLog`), query filtering, and real-time frontend transition controls and history timelines.
- Alembic migrations run before the backend in Docker Compose. CI runs backend
  migration/tests and frontend lint/build.

## Remaining gaps

### CRM and customer workflows

- Lead capture does not yet include budget, purchase timeline, conversation
  reference, or a full activity/history timeline.
- Automated lead assignment rules, deal management, customer preferences, and
  lead-retention/deletion policies are not implemented.
- Lead collections use bounded `limit`/`offset` parameters but do not yet return
  the shared pagination metadata used by some other endpoints.

### Assistant and communications

- Assistant messages and conversations are not persisted server-side. The
  browser currently sends bounded history with each request.
- There is no staff conversation inbox, handoff/callback queue, or customer
  cross-channel identity resolution.
- WhatsApp, voice, notifications, and booking reminders are not integrated.
- Assistant conversation IDs and message-level audit/retention controls remain
  to be designed.

### Inventory, reporting, and governance

- Staff availability, multi-location operations, and sales deals are absent.
- Audit events cover selected workflows, not every sensitive mutation.
- Reporting and workflow observability are limited; no event outbox or
  notification-delivery ledger exists.

### Security and operations

- Browser access and refresh tokens remain in `localStorage`; an XSS-safe
  HttpOnly-cookie design is still needed.
- Idempotency response storage and locking are process-local, so replay
  protection is not shared across workers or durable across restarts.
- Account lockout, end-user email verification, and formal data-retention
  tooling are not implemented.
- Production secrets, Supabase bucket policies, email delivery, database
  backups, and monitoring must be configured and verified per deployment.

## Priority next steps

1. Persist assistant conversations and connect consented leads to their
   conversation records.
2. Add inventory lifecycle states/history and broaden mutation audit coverage.
3. Move auth tokens to secure HttpOnly cookies and make idempotency storage
   shared/durable before horizontal scaling.
4. Add lead budget/timeline/activity fields, automated assignment options, and
   retention controls.
5. Add staff handoff, reminders, workflow outbox/observability, and focused
   frontend interaction tests.

## Related documents

- [Overview](overview.md)
- [Architecture](architecture.md)
- [Deployment](deployment.md)
- [Development Guide](development.md)
- [Functional Requirements](functional-requirements.md)
