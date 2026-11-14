# DealerDesk / AutoPilot AI Project Execution Plan

## 1. Purpose

This document is the implementation plan for DealerDesk, based on
`AutoPilot_AI_Project_Specification (2).pdf`. It defines the order in which the
product will be built, the evidence required to complete each phase, and the
rules that keep the project within the Version 1 boundary.

The implementation target is a portfolio-grade simulated dealership platform.
The first reliable channel is website chat. WhatsApp and browser voice are
adapter-based additions with simulator fallbacks. Real payments, financing,
PSTN telephony, service management, and customer-built n8n workflows are not
Version 1 deliverables.

## 2. Delivery principles

1. **Build one vertical slice first.** A user must be able to sign in, browse
   seeded Honda and Toyota inventory, ask a grounded question, create a lead,
   and book a test drive before additional channels or advanced agents are
   added.
2. **The backend owns business truth.** FastAPI validates and persists
   inventory, leads, bookings, permissions, and state transitions. Agents and
   n8n may request operations but must not implement their own business rules.
3. **Keep AI replaceable.** LLM, embedding, messaging, and voice integrations
   use provider interfaces. Mock providers must support local development and
   automated tests.
4. **Enforce isolation server-side.** Every tenant-owned query and mutation is
   scoped by dealership and, where applicable, brand. UI visibility is never
   treated as authorization.
5. **Make writes safe.** State-changing tools require validated arguments,
   explicit confirmation where appropriate, database transactions, idempotency,
   audit records, and retry-safe events.
6. **Prefer demonstrable reliability over feature count.** Every milestone
   ends with tests and a runnable local demonstration.

## 3. Target architecture

| Area | Implementation direction |
| --- | --- |
| Web | Next.js and TypeScript for customer chat and staff control center |
| API | FastAPI, Pydantic schemas, service/repository boundaries, OpenAPI |
| Database | PostgreSQL with migrations; pgvector for knowledge retrieval |
| Agent runtime | LangGraph router and brand-scoped agents |
| Automation | Self-hosted n8n; backend domain events delivered through a durable outbox |
| Background work | FastAPI worker/background processing initially; introduce a queue only when needed |
| Local environment | Docker Compose for API, web, PostgreSQL/pgvector, and n8n |
| Observability | Structured logs with request, tenant, conversation, event, and workflow identifiers |

The repository currently contains a `backend/` FastAPI application and a
`frontend/` application. New capabilities should extend those areas rather
than introducing a second application layout. As the codebase grows, keep
agent runtime, knowledge processing, and provider adapters in clearly
separated modules or services.

## 4. Milestones and exit criteria

### Phase 0 - Foundation

**Build:** Docker Compose, environment configuration, PostgreSQL/pgvector,
migrations, health checks, structured logging, API versioning, frontend shell,
and seeded demo data.

**Exit criteria:**

- One documented command starts the local stack.
- Database migrations and seed scripts are repeatable.
- Health endpoints report dependency status.
- Basic authentication works with a seeded dealership user.
- Secrets are loaded from environment variables and are not committed.

### Phase 1 - Dealership core

**Build:** dealership, user, role, brand, vehicle model, variant, and inventory
models; authenticated catalog and inventory APIs; staff inventory screens.

**Exit criteria:**

- Staff can browse and update seeded Honda and Toyota inventory.
- Inventory status is limited to `available`, `reserved`, `sold`, and
  `unavailable`.
- Tenant and role authorization tests pass.
- Status changes are auditable.

### Phase 2 - Website chat

**Build:** conversation and message APIs, customer chat UI, persisted
conversation history, channel adapter contract, and provider-neutral LLM
adapter with a mock implementation.

**Exit criteria:**

- A customer can start and resume a website conversation.
- Every message stores channel, timestamps, and external identifiers where
  available.
- Provider failure preserves the conversation and offers human handoff.
- The chat clearly identifies AI interaction and follows consent rules.

### Phase 3 - Knowledge and agents

**Build:** text/PDF ingestion, document versions, chunking, embeddings,
tenant/brand-filtered retrieval, reception router, and Honda/Toyota sales
agents.

**Exit criteria:**

- Approved answers include retrievable source metadata.
- Catalog facts come from structured data or approved knowledge.
- Wrong-brand retrieval tests pass.
- Ambiguous brand/model requests produce a clarification question.
- At least 30 version-controlled evaluation scenarios are executable.

### Phase 4 - Business tools

**Build:** narrow backend tools for catalog search, inventory availability,
lead capture, slot lookup, booking, cancellation/rescheduling, and escalation.

**Exit criteria:**

- The agent can complete inquiry -> qualification -> consented lead creation.
- Available slots are computed from business hours, capacity, and bookings.
- Booking rechecks availability in a transaction.
- Duplicate booking requests with the same idempotency key return the original
  result.
- Every write has validated arguments and an audit record.

### Phase 5 - n8n automation

**Build:** signed domain-event webhooks, durable event/outbox processing, n8n
lead assignment, booking confirmation, reminders, follow-up, and inventory
waitlist workflows.

**Exit criteria:**

- Events include stable IDs and are retry-safe.
- n8n downtime does not roll back a committed business transaction.
- Duplicate events do not duplicate messages or tasks.
- Opted-out customers receive no promotional follow-up.
- Workflow status and error summaries are visible without exposing secrets.

### Phase 6 - Additional channels

**Build:** WhatsApp sandbox or simulator adapter and browser voice interaction.
Keep channel-specific parsing and delivery outside agent/business logic.

**Exit criteria:**

- At least one additional channel works end-to-end.
- External identifiers and channel metadata are persisted.
- The simulator can run without paid provider credentials.
- Provider failures have a visible retry or handoff path.

### Phase 7 - Control center

**Build:** agent configuration, knowledge management, conversation inbox, CRM
lead pipeline, booking management, and basic analytics.

**Exit criteria:**

- Managers can configure enabled agents, brand scope, prompt version, language,
  and tools.
- Staff can inspect transcripts, sources, tool calls, leads, bookings, and
  workflow executions.
- Analytics show channel volume, leads, bookings, handoffs, failures, and
  latency.
- Important actions appear in the audit trail.

### Phase 8 - Hardening and portfolio demo

**Build:** evaluation reporting, failure-path coverage, deployment guide,
architecture/API/ER diagrams, demo seed data, and a short demonstration video.

**Exit criteria:**

- A clean checkout can reproduce the local demo.
- Unit, integration, contract, end-to-end, and AI evaluation suites have
  documented results.
- Tenant isolation, duplicate events, booking conflicts, provider failure, and
  opt-out scenarios are demonstrated.
- The main demo shows chat -> grounded answer -> inventory -> lead -> booking
  -> n8n confirmation/reminder.

## 5. Work execution rules

For each feature:

1. Define the user journey and acceptance examples.
2. Add or update the database migration and typed schemas.
3. Implement repository queries with tenant and brand filters.
4. Add service-layer business rules and audit/event behavior.
5. Expose the smallest API contract needed by the UI or agent tool.
6. Add focused tests before connecting external providers.
7. Implement UI, agent, or workflow integration.
8. Run the milestone exit criteria and update API/OpenAPI documentation.

Pull requests should be small enough to review by one capability. Do not
combine channel integration, data model changes, and unrelated UI work in one
change unless they are required for the same vertical slice.

## 6. Quality gates

- **Security:** no committed secrets; server-side role and tenant checks;
  signed webhooks; safe logging.
- **Correctness:** inventory and booking writes are transactional; availability
  is checked at booking time; event and booking operations are idempotent.
- **AI safety:** no invented price, stock, policy, or slot; uncertainty leads to
  retrieval, clarification, or human handoff.
- **Testing:** core rules run without an LLM or external provider; adapters have
  mocks; failure tests cover provider timeouts and malformed/duplicate events.
- **Performance:** ordinary database-backed API endpoints target p95 under
  500 ms in local/demo conditions, excluding LLM and external-provider latency.
- **Accessibility:** keyboard navigation, readable contrast, responsive layouts,
  and clear consent/opt-out controls.

## 7. Definition of Version 1 complete

Version 1 is complete when a customer can use website chat to ask about a
Honda or Toyota vehicle, receive a source-grounded answer, check seeded
inventory, create a consented lead, and book a test drive. FastAPI validates
and persists every business operation, n8n handles confirmation and follow-up,
and dealership staff can inspect the conversation, sources, tools, lead,
booking, and workflow result. WhatsApp and browser voice may use real sandbox
providers or documented simulator fallbacks.
