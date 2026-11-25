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
  vehicle interest, budget, purchase timeline, conversation reference,
  customer preferences, deal value/notes, automated round-robin lead
  assignment, full lead activity/history timeline (`LeadActivity`), shared
  pagination metadata headers (`X-Total-Count`, `X-Page`, `X-Page-Size`,
  `X-Total-Pages`), lead deletion/retention policies, and matching test-drive
  booking linkage. Direct test-drive bookings auto-link or create CRM leads,
  and booked leads can transition to `won`, `follow_up`, or `lost` with
  double-sale protection, automatic `sold` stock sync, and cleanup of future
  slots, active holds, and competing bookings.
- Multi-channel AI Sales Agent across Website, Twilio WhatsApp Sandbox, and
  Vapi Voice AI with server-side conversation persistence, slot holds,
  single-use OTP booking verification, and a Staff Conversation Inbox &amp;
  Human Handoff/Callback Queue UI (`/inbox`).
- Frontend pages call the backend APIs and report loading and request errors;
  customer and staff workflows are role-aware.
- Inventory lifecycle management supporting rich states (`available`, `reserved`, `sold`, `in_transit`, `unavailable`), audited status transitions (`VehicleStatusHistory`), audit log integration (`AuditLog`), query filtering, and real-time frontend transition controls and history timelines.
- Transactional HTML & plain-text email notification system (powered by Resend) covering account verification, password reset & change alerts, staff invitations, OTP verification, dealership welcome, test-drive booking/reschedule/cancellation confirmations, automated 24h/2h test-drive reminders (`reminder_service` + `run_booking_reminders.py` CLI), a PostgreSQL `NotificationDelivery` ledger with idempotent uniqueness, customer lead acknowledgments, dealership new-lead alerts, and staff lead-assignment notifications.
- Account brute-force lockout, end-user email verification, XSS-safe
  `HttpOnly` cookie session management (`dd_access` / `dd_refresh`),
  DB-backed idempotency middleware, automatic PII scrubbing on transcript
  ingestion, staff message-level redaction, and data-retention cleanup tooling
  (including aged transcript PII redaction and closed conversation pruning).
- Transactional async event outbox (`OutboxEvent`) with HMAC-signed webhook
  delivery, exponential backoff retries, dead-letter tracking, dealership
  summary reporting (`/reports/summary`), staff availability flags (`is_available`
  respected by automated lead assignment), and expanded granular audit logging.
- Alembic migrations run before the backend in Docker Compose. CI runs backend
  migration/tests and frontend lint/build.

## Remaining gaps

### Inventory, reporting, and governance

- Multi-location branch hierarchies and full third-party lender/financing
  desking remain future product expansions.

### Security and operations

- Production secrets, Supabase bucket policies, email delivery, database
  backups, and monitoring must be configured and verified per deployment.

## Priority next steps

1. Add focused frontend interaction tests and expand multi-location /
   lender-financing workflows as needed.

## Related documents

- [Overview](overview.md)
- [Architecture](architecture.md)
- [Deployment](deployment.md)
- [Development Guide](development.md)
- [Functional Requirements](functional-requirements.md)
