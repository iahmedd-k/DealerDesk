# DealerDesk / AutoPilot AI Functional Requirements

## 1. Scope

These requirements are derived from
`AutoPilot_AI_Project_Specification (2).pdf` and define the behavior to build
for Version 1. The backend is authoritative for business state and
authorization. Website chat is the primary MVP channel; WhatsApp and voice
are adapter-based extensions.

## 2. Actors and roles

| Actor | Responsibilities |
| --- | --- |
| Platform administrator (`dealerdesk_admin`) | Manages all dealerships/workspaces across the platform, monitors system health, global user inspection |
| Dealership administrator (`dealership_admin`) | Manages dealership workspace, staff, brands, inventory, agents, knowledge, and reporting |
| Manager (`manager`) | Assigns leads, manages bookings, monitors conversations and workflows |
| Sales representative (`sales_rep`) | Works assigned leads, updates status, manages test drives, takes over conversations |
| Customer (`customer`) | Asks questions, receives recommendations, submits contact details, and books/reschedules/cancels test drives |

## 3. Functional requirements

### Identity, tenancy, and catalog

| ID | Requirement | Acceptance statement | Status |
| --- | --- | --- | --- |
| FR-001 | Authentication and roles | Users can sign in and receive access appropriate to `dealerdesk_admin`, `dealership_admin`, `manager`, `sales_rep`, or `customer`. | **Implemented** |
| FR-002 | Dealership workspace | Authorized dealership administrators can view and update profile, contact details, business hours, and supported channels. Platform admin can list all workspaces. | **Implemented** |
| FR-003 | Brand and vehicle catalog | Staff can manage brands, models, model years, variants, specifications, features, published vehicle content, and ordered vehicle images. | **Implemented** |
| FR-004 | Inventory management | Staff can add stock units and update status among `available`, `reserved`, `sold`, and `unavailable`; each change is recorded. | **Implemented** |

### Knowledge and conversations

| ID | Requirement | Acceptance statement | Status |
| --- | --- | --- | --- |
| FR-005 | Knowledge ingestion | Authorized staff can upload supported text/PDF documents; the system extracts, chunks, embeds, and indexes them by dealership and brand. | **Implemented** |
| FR-006 | Knowledge retrieval | Agents retrieve relevant chunks with source metadata; factual vehicle answers use retrieved content or structured catalog data. | **Implemented** |
| FR-007 | Conversation channels | Website chat is supported in MVP; WhatsApp and voice use defined adapters. Messages store channel, external identifiers, and timestamps. | Planned |
| FR-008 | Conversation continuity | Conversation history and customer context can resume; cross-channel association requires a reliable identifier or explicit matching. | Planned |
| FR-009 | Intent routing | A router identifies intent and brand/model, routes to the right specialist, and asks for clarification when ambiguous. | Planned |
| FR-010 | Brand-scoped agents | Each agent can access only its authorized dealership and brand knowledge/tools; brand content must not be mixed. | Planned |
| FR-011 | Agent tool calling | Agents can call approved tools for catalog search, inventory, lead creation, slot lookup, booking, and escalation. | Planned |
| FR-012 | Vehicle search and recommendation | Customers can search or receive recommendations by brand, model, budget, and preferences using backend data. | Planned |

### Leads and test drives

| ID | Requirement | Acceptance statement | Status |
| --- | --- | --- | --- |
| FR-013 | Lead capture | With consent, the system creates a lead containing contact details, vehicle interest, budget, timeline, channel, and conversation reference. | Planned |
| FR-014 | Lead management | Staff can view, assign, filter, and update lead status: `new`, `contacted`, `qualified`, `test_drive_scheduled`, `won`, `lost`, or `follow_up`. | Planned |
| FR-015 | Lead assignment | Managers can assign leads manually; configurable brand or round-robin rules can assign new leads to available representatives. | Planned |
| FR-016 | Test-drive availability | The backend exposes slots based on business hours, capacity, and existing bookings. Supports query filters by vehicle, date range, and availability. | **Implemented** |
| FR-017 | Test-drive booking | Customers book only after explicit confirmation; backend concurrency validation prevents over-capacity, double booking, and overlapping times. | **Implemented** |
| FR-018 | Booking management | Authorized staff can view, reschedule, and cancel bookings across the dealership. Customer changes use demo-appropriate identity/contact verification. | **Implemented** |
| FR-019 | Human handoff | Customers can request a human; low confidence, repeated failure, complaints, and policy triggers preserve the transcript and create/update a callback task. | Planned |

### Events and automation

| ID | Requirement | Acceptance statement |
| --- | --- | --- |
| FR-020 | n8n event integration | Backend emits signed events for `lead.created`, `lead.assigned`, `test_drive.booked`, `test_drive.cancelled`, and `inventory.updated`. |
| FR-021 | Lead notification workflow | n8n notifies the assigned representative and acknowledges the customer through configured adapters, subject to preferences. |
| FR-022 | Booking reminders | n8n schedules or triggers reminders and records delivery status without duplicate reminders. |
| FR-023 | Follow-up workflow | n8n creates a task or approved follow-up after inquiry/test drive, respecting opt-out, conversion, closure, and attempt limits. |
| FR-024 | Workflow observability | Staff can see event/workflow status, last result, and safe error summaries without secrets. |

### Staff control center and governance

| ID | Requirement | Acceptance statement |
| --- | --- | --- |
| FR-025 | Agent management | Dealership administrators can create, edit, test, enable, and disable agents and configure brand scope, prompt version, language, and tools. |
| FR-026 | Knowledge management | Staff can upload, list, deactivate, and replace documents and see processing status and version. |
| FR-027 | Conversation inbox | Staff can search conversations, inspect summaries/transcripts, see related leads/bookings, and take ownership. |
| FR-028 | Basic analytics | Dashboard reports conversation count by channel, leads, bookings, handoffs, agent failures, and response latency. |
| FR-029 | Audit trail | Important staff and agent actions record actor, tenant, action, resource, timestamp, and outcome. |
| FR-030 | Evaluation suite | Developers can run test conversations and inspect retrieval relevance, tool selection, answer correctness, and escalation behavior. |
| FR-031 | Provider configuration | LLM, embedding, messaging, and voice providers are accessed through replaceable interfaces and mock implementations. |
| FR-032 | Customer opt-out | Customers can opt out of promotional/follow-up messages; transactional communication follows channel rules and preferences. |

## 4. Required user journeys

### Inquiry to lead

1. Customer starts website chat or WhatsApp.
2. Router identifies intent and brand/model or asks a clarification.
3. Brand agent retrieves approved content and structured catalog data.
4. Availability and price come from backend tools, never model guesses.
5. Agent asks qualification questions.
6. After consent, backend creates the lead and returns a reference.
7. Conversation and customer context remain available to staff.

### Lead to test drive

1. Customer requests a model test drive.
2. Agent collects required details and preferred time.
3. Backend returns available slots.
4. Agent presents choices and receives explicit confirmation.
5. Backend validates capacity, writes the booking transactionally, and applies
   an idempotency key.
6. `test_drive.booked` is emitted only after commit.
7. n8n sends confirmation and schedules a reminder.

### Human handoff

1. Customer requests a human or the agent reaches a confidence/policy trigger.
2. Agent explains the handoff.
3. Backend stores a summary and creates/updates a callback task.
4. n8n notifies the assigned staff member.
5. Staff sees transcript, customer, vehicle, and escalation reason.

### Inventory waitlist

1. Staff changes a vehicle to available.
2. Backend commits the update and emits `inventory.updated`.
3. n8n finds exact matching active waitlist entries.
4. Approved notifications or staff tasks are created once.
5. Event and workflow outcomes are retained for inspection.

## 5. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | Secrets use environment variables or a secret manager and never reach source control or frontend clients. |
| NFR-002 | Every protected operation performs server-side role and tenant authorization. |
| NFR-003 | Every tenant-owned record is scoped by `dealership_id`; cross-tenant tests are mandatory. |
| NFR-004 | Collect only data needed for inquiry, lead, and booking workflows; document retention/deletion behavior. |
| NFR-005 | Explain AI interaction and obtain required consent for recording or follow-up. |
| NFR-006 | Webhooks validate signatures, are idempotent, retry transient failures, and retain failed events. |
| NFR-007 | Inventory and booking state changes use transactions and recheck availability at booking time. |
| NFR-008 | Target p95 under 500 ms for ordinary database-backed local/demo API requests, excluding providers and LLMs. |
| NFR-009 | Record AI response/tool latency and stream responses where supported. |
| NFR-010 | Docker Compose is the reliable local reference environment; hosted free tiers are optional. |
| NFR-011 | Prefer stateless API instances, background processing for ingestion/notifications, and pagination. |
| NFR-012 | Use typed schemas, modular services, repository boundaries, migrations, structured logs, and documented API contracts. |
| NFR-013 | Attach request, conversation, tenant, and event/workflow IDs to relevant logs and traces. |
| NFR-014 | Agents must not invent prices, stock, slots, or policies; unknown facts require retrieval, clarification, or handoff. |
| NFR-015 | Tools are narrow and authorized; state-changing tools validate arguments and require confirmation where applicable. |
| NFR-016 | Core rules run without an LLM/provider; provider adapters support mocks. |
| NFR-017 | Dashboard and chat support keyboard navigation, readable contrast, and responsive layouts. |
| NFR-018 | Track provider/token usage where available and apply low quotas and hard free-tier limits. |

## 6. Definition of done

A requirement is done only when its API/service behavior, authorization,
persistence, UI or agent integration, focused tests, and failure behavior are
implemented. The requirement must also be demonstrable locally using seeded
data or a documented simulator; a provider-only happy path is not sufficient.

## 7. Version 1 exclusions

Do not add real payment processing, deposits/refunds, loan approval, financial
advice, credit scoring, full service-center management, accounting/ERP
workflows, customer-facing n8n workflow editing, required paid PSTN telephony,
guaranteed production WhatsApp delivery on a free plan, autonomous negotiation,
or advanced predictive lead scoring.
