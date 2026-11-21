# DealerDesk System Architecture and Data Model

This document explains the planned DealerDesk / AutoPilot AI system from the
functional requirements and project execution plan. It is intentionally written
as a normal Markdown document so it can be read in GitHub, VS Code, or any
Mermaid-compatible Markdown viewer.

> **Implementation status:** The target model below describes Version 1
> requirements. The initial workspace phase now implements customer
> registration, dealership registration, dealership-admin creation, staff
> invitation records, vehicle management, test-drive settings, and
> idempotent slot generation. Chat, WhatsApp, voice, leads, bookings, and n8n
> automation remain later phases.

## 1. System at a glance

DealerDesk is a multi-tenant dealership platform with two main experiences:

1. **Customer experience:** a customer asks questions through website chat
   (MVP), receives grounded vehicle information, checks inventory, submits
   contact details, and books or changes a test drive.
2. **Staff control center:** dealership staff manage inventory, leads,
   conversations, agents, knowledge, bookings, workflows, and reports.

The backend is the source of truth. AI agents, channel adapters, and n8n
automation request operations from the backend; they do not own business state.

```mermaid
flowchart LR
    Customer[Customer]
    Staff[Dealership staff]
    Admin[Platform administrator]

    subgraph Channels["Customer channels"]
        WebChat[Website chat MVP]
        WhatsApp[WhatsApp adapter]
        Voice[Browser voice adapter]
    end

    subgraph App["DealerDesk application"]
        Web[Customer web app]
        Console[Staff control center]
        API[FastAPI backend API]
        Auth[Authentication and authorization]
        Domain[Domain services and business rules]
        Agent[Router and brand-scoped agents]
        Tools[Authorized agent tools]
        Knowledge[Knowledge ingestion and retrieval]
        Events[Transactional event and outbox layer]
    end

    subgraph Data["Authoritative data"]
        DB[(PostgreSQL + pgvector)]
        Files[(Document storage)]
    end

    subgraph Automation["Automation"]
        N8N[n8n workflows]
        Notify[Email / channel notification adapters]
    end

    Customer --> WebChat
    Customer --> WhatsApp
    Customer --> Voice
    WebChat --> Web
    WhatsApp --> Web
    Voice --> Web
    Web --> API
    Staff --> Console
    Admin --> Console
    Console --> API
    API --> Auth
    API --> Domain
    Domain --> Agent
    Agent --> Tools
    Tools --> Domain
    Domain --> Knowledge
    Knowledge --> DB
    Knowledge --> Files
    Domain --> DB
    Domain --> Events
    Events --> N8N
    N8N --> Notify
    Notify --> WhatsApp
    Notify --> Customer
```

### Core ownership rules

| Area | Owner of truth | Important rule |
| --- | --- | --- |
| Users, roles, tenancy | Backend database | Every protected request checks role and dealership scope server-side. |
| Catalog and inventory | Backend domain services | Price and stock are read from backend data, never guessed by an agent. |
| Leads and bookings | Backend domain services | Writes are validated, transactional, auditable, and idempotent where needed. |
| Conversation history | Backend database | Messages retain channel, timestamps, external IDs, and conversation context. |
| Knowledge | Ingestion and retrieval services | Retrieval is filtered by dealership and brand. |
| Notifications and follow-up | n8n | n8n reacts to committed backend events and must be retry-safe. |
| AI providers | Provider adapters | LLM and embedding providers are replaceable and have mock implementations. |

## 2. Target entity relationship diagram

This is the logical Version 1 model implied by the functional requirements.
Foreign keys should include `dealership_id` on tenant-owned records, either
directly or through an owning entity, and queries must enforce that scope.

```mermaid
erDiagram
    DEALERSHIP ||--o{ USER : employs
    USER }o--o{ ROLE : receives
    DEALERSHIP ||--o{ BRAND : owns
    BRAND ||--o{ VEHICLE_MODEL : contains
    VEHICLE_MODEL ||--o{ VEHICLE_VARIANT : has
    VEHICLE_VARIANT ||--o{ INVENTORY_UNIT : stocked_as
    DEALERSHIP ||--o{ INVENTORY_UNIT : holds
    INVENTORY_UNIT ||--o{ INVENTORY_STATUS_HISTORY : records
    USER ||--o{ INVENTORY_STATUS_HISTORY : changes

    DEALERSHIP ||--o{ AGENT : configures
    BRAND ||--o{ AGENT : scopes
    AGENT ||--o{ AGENT_TOOL : permits
    DEALERSHIP ||--o{ KNOWLEDGE_DOCUMENT : owns
    BRAND ||--o{ KNOWLEDGE_DOCUMENT : scopes
    KNOWLEDGE_DOCUMENT ||--o{ KNOWLEDGE_CHUNK : produces

    CUSTOMER ||--o{ CONVERSATION : starts
    DEALERSHIP ||--o{ CONVERSATION : receives
    CONVERSATION ||--o{ MESSAGE : contains
    CONVERSATION }o--o{ AGENT : handled_by
    CONVERSATION ||--o{ HANDOFF_TASK : escalates_to

    CUSTOMER ||--o{ LEAD : creates
    DEALERSHIP ||--o{ LEAD : owns
    LEAD }o--o{ USER : assigned_to
    LEAD }o--o{ VEHICLE_VARIANT : interests_in
    LEAD }o--o{ CONVERSATION : references

    CUSTOMER ||--o{ TEST_DRIVE_BOOKING : makes
    DEALERSHIP ||--o{ TEST_DRIVE_BOOKING : schedules
    INVENTORY_UNIT |o--o{ TEST_DRIVE_BOOKING : may_use
    VEHICLE_VARIANT ||--o{ TEST_DRIVE_BOOKING : concerns
    LEAD |o--o{ TEST_DRIVE_BOOKING : leads_to

    CUSTOMER ||--o{ COMMUNICATION_PREFERENCE : sets
    DEALERSHIP ||--o{ DOMAIN_EVENT : emits
    DOMAIN_EVENT ||--o{ WORKFLOW_EXECUTION : triggers
    DEALERSHIP ||--o{ AUDIT_LOG : records
    USER |o--o{ AUDIT_LOG : performs
    AGENT |o--o{ AUDIT_LOG : performs

    DEALERSHIP {
        uuid id PK
        string name
        string contact_details
        json business_hours
        json supported_channels
        datetime created_at
    }

    USER {
        int id PK
        uuid dealership_id FK
        string name
        string email UK
        string password_hash
        boolean is_active
        datetime created_at
    }

    ROLE {
        uuid id PK
        string code
        string description
    }

    BRAND {
        uuid id PK
        uuid dealership_id FK
        string name
        boolean is_active
    }

    VEHICLE_MODEL {
        uuid id PK
        uuid brand_id FK
        string name
        string model_year
        text published_content
    }

    VEHICLE_VARIANT {
        uuid id PK
        uuid vehicle_model_id FK
        string name
        json specifications
        json features
        decimal price
    }

    INVENTORY_UNIT {
        uuid id PK
        uuid dealership_id FK
        uuid vehicle_variant_id FK
        string stock_number UK
        string status
        decimal asking_price
        datetime updated_at
    }

    INVENTORY_STATUS_HISTORY {
        uuid id PK
        uuid inventory_unit_id FK
        int changed_by_user_id FK
        string old_status
        string new_status
        datetime changed_at
    }

    AGENT {
        uuid id PK
        uuid dealership_id FK
        uuid brand_id FK
        string name
        string prompt_version
        string language
        boolean enabled
    }

    AGENT_TOOL {
        uuid id PK
        uuid agent_id FK
        string tool_name
        boolean enabled
    }

    KNOWLEDGE_DOCUMENT {
        uuid id PK
        uuid dealership_id FK
        uuid brand_id FK
        string filename
        string version
        string processing_status
        boolean active
    }

    KNOWLEDGE_CHUNK {
        uuid id PK
        uuid document_id FK
        text content
        vector embedding
        json source_metadata
    }

    CUSTOMER {
        uuid id PK
        string name
        string email
        string phone
        string external_identifier
        datetime created_at
    }

    CONVERSATION {
        uuid id PK
        uuid dealership_id FK
        uuid customer_id FK
        string channel
        string external_conversation_id
        string status
        uuid assigned_agent_id FK
        datetime started_at
        datetime last_message_at
    }

    MESSAGE {
        uuid id PK
        uuid conversation_id FK
        string direction
        string external_message_id
        text content
        json metadata
        datetime created_at
    }

    LEAD {
        uuid id PK
        uuid dealership_id FK
        uuid customer_id FK
        uuid conversation_id FK
        uuid vehicle_variant_id FK
        int assigned_user_id FK
        string status
        string budget
        string timeline
        boolean consented
        datetime created_at
    }

    TEST_DRIVE_BOOKING {
        uuid id PK
        uuid dealership_id FK
        uuid customer_id FK
        uuid lead_id FK
        uuid vehicle_variant_id FK
        uuid inventory_unit_id FK
        datetime starts_at
        datetime ends_at
        string status
        string idempotency_key UK
        datetime created_at
    }

    COMMUNICATION_PREFERENCE {
        uuid id PK
        uuid customer_id FK
        string channel
        boolean promotional_opt_out
        datetime updated_at
    }

    HANDOFF_TASK {
        uuid id PK
        uuid conversation_id FK
        uuid assigned_user_id FK
        string reason
        string status
        datetime created_at
    }

    DOMAIN_EVENT {
        uuid id PK
        uuid dealership_id FK
        string event_type
        string aggregate_type
        uuid aggregate_id
        json payload
        string delivery_status
        datetime created_at
    }

    WORKFLOW_EXECUTION {
        uuid id PK
        uuid domain_event_id FK
        string workflow_name
        string status
        string safe_error_summary
        datetime started_at
        datetime completed_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid dealership_id FK
        int actor_user_id FK
        uuid actor_agent_id FK
        string action
        string resource_type
        uuid resource_id
        string outcome
        datetime created_at
    }
```

### Relationship interpretation

- One dealership owns its staff, brands, inventory, agents, knowledge, leads,
  conversations, bookings, events, and audit records.
- A brand belongs to one dealership. An agent and knowledge document may be
  scoped to a brand; this prevents cross-brand answers.
- A vehicle model has many variants, and each variant can have multiple stock
  units. Inventory status is one of `available`, `reserved`, `sold`, or
  `unavailable`.
- A conversation contains immutable message history and may produce a lead,
  booking, or human-handoff task.
- A booking may be associated with a lead and a specific inventory unit, but
  availability is ultimately validated against business hours, capacity, and
  existing bookings.
- A committed business change creates a domain event. n8n records its workflow
  result separately, allowing retries and operational visibility.

## 3. Main customer flow: inquiry to lead

```mermaid
sequenceDiagram
    actor Customer
    participant Channel as Website chat / channel adapter
    participant API as FastAPI backend
    participant Router as Intent and brand router
    participant Agent as Brand-scoped agent
    participant Tools as Authorized tools
    participant DB as Database
    participant Staff as Staff inbox

    Customer->>Channel: Ask vehicle question
    Channel->>API: Send message with channel metadata
    API->>DB: Create or resume conversation
    API->>Router: Classify intent and brand/model
    alt Ambiguous brand or model
        Router-->>API: Request clarification
        API-->>Channel: Ask customer to clarify
    else Brand identified
        Router->>Agent: Route to authorized brand agent
        Agent->>Tools: Retrieve knowledge and catalog data
        Tools->>DB: Query dealership and brand-scoped data
        DB-->>Tools: Approved content, price, and inventory
        Tools-->>Agent: Grounded results with source metadata
        Agent-->>API: Answer and ask qualification questions
        API-->>Channel: Return response
        Customer->>Channel: Provide details and consent
        Channel->>API: Submit lead details
        API->>DB: Create consented lead and link conversation
        DB-->>API: Lead reference
        API-->>Channel: Confirm lead creation
        API-->>Staff: Lead and conversation become visible
    end
```

## 4. Main customer flow: lead to test drive

```mermaid
flowchart TD
    A[Customer requests a test drive] --> B[Agent collects model, contact details, and preferred time]
    B --> C[Backend checks dealership hours, capacity, and existing bookings]
    C --> D{Slots available?}
    D -- No --> E[Offer alternatives or create follow-up task]
    D -- Yes --> F[Present available slots]
    F --> G[Customer explicitly confirms a slot]
    G --> H[Backend rechecks availability in a transaction]
    H --> I{Still available?}
    I -- No --> F
    I -- Yes --> J[Create booking with idempotency key]
    J --> K[Commit booking and audit record]
    K --> L[Emit test_drive.booked after commit]
    L --> M[n8n sends confirmation]
    M --> N[n8n schedules reminder without duplicates]
```

The same transactional pattern applies to cancellation and rescheduling.
The backend, not the agent or n8n, decides whether the booking is valid.

## 5. Human handoff flow

```mermaid
flowchart LR
    Trigger[Customer requests human, low confidence, complaint, or policy trigger]
    Explain[Agent explains handoff]
    Persist[Backend stores summary and preserves transcript]
    Task[Create or update callback task]
    Assign[Manager or configured assignment rule]
    Notify[n8n notifies assigned staff member]
    Inbox[Staff sees transcript, customer, vehicle, and reason]

    Trigger --> Explain --> Persist --> Task --> Assign --> Notify --> Inbox
```

## 6. Inventory waitlist flow

```mermaid
flowchart TD
    Staff[Staff changes inventory to available]
    API[Backend validates role and dealership scope]
    Tx[Commit inventory status and status history]
    Event[Emit inventory.updated]
    Match[n8n finds exact active waitlist matches]
    Deduplicate[Check event and notification idempotency]
    Notify[Send approved notification or create staff task]
    Observe[Retain event and workflow outcome]

    Staff --> API --> Tx --> Event --> Match --> Deduplicate --> Notify --> Observe
```

## 7. Authentication and request authorization

The current authentication flow is already present in the backend:

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI /api/v1/auth
    participant Repo as User repository
    participant DB as SQL database
    participant Auth as Auth service

    User->>API: POST /auth/signup
    API->>Repo: Check email
    Repo->>DB: SELECT user by email
    DB-->>Repo: Existing user or none
    API->>Auth: Hash password
    API->>Repo: Create user
    Repo->>DB: INSERT users and commit
    DB-->>API: New user
    API-->>User: 201 user profile

    User->>API: POST /auth/login
    API->>Repo: Find normalized email
    Repo->>DB: SELECT users
    DB-->>API: User record
    API->>Auth: Verify password and create JWT
    API-->>User: Bearer access token

    User->>API: Protected request with bearer token
    API->>Auth: Validate signature, expiry, and revocation
    Auth->>DB: Load user by token subject
    DB-->>Auth: User
    Auth-->>API: Current user
    API-->>User: Authorized response
```

Current code locations:

- Application startup and router registration: `backend/app/main.py`
- Versioned API router: `backend/app/api/v1/router.py`
- Signup, login, logout, and current-user endpoints:
  `backend/app/api/v1/endpoints/auth.py`
- JWT and password operations: `backend/app/services/auth_service.py`
- User lookup and creation: `backend/app/repositories/user_repository.py`
- Current implemented SQLAlchemy model: `backend/app/models/user.py`

## 8. Current implementation versus target

| Capability | Current repository | Target described by requirements |
| --- | --- | --- |
| FastAPI app and versioned API | Implemented | Keep as API foundation |
| PostgreSQL database (Supabase/local) | Implemented | PostgreSQL + startup migrations + transaction pooler |
| User signup/login/logout/me & RBAC | Implemented | `dealerdesk_admin`, `dealership_admin`, `manager`, `sales_rep`, and `customer` |
| Dealership and staff management | Implemented | Workspace lifecycle, staff invitations, role revocation, last-admin guard |
| Brands and vehicle inventory | Implemented | Multi-brand support (up to 20), vehicle inventory CRUD, test-drive flags |
| Knowledge ingestion and retrieval | Implemented | PDF/text extraction, chunking, OpenAI-compatible or local embeddings, search |
| Test-drive slots and availability | Implemented | Timezone/DST slot generation, capacity tracking, remaining capacity, query filters |
| Test-drive bookings & management | Implemented | Concurrency locking, duplicate prevention, staff view/reschedule/cancel, customer verification |
| Website chat and conversations | Planned | Add channel adapters, messages, continuity, and consent |
| Agent routing and tools | Planned | Add router, brand agents, and narrow authorized tools |
| Leads management | Planned | Add lead capture, manual/round-robin assignment, and status lifecycle |
| n8n events and workflows | Planned | Add signed outbox events, retries, and workflow status |
| Staff control center and analytics | Planned | Add inbox, CRM, agent/knowledge management, and reporting |

### Initial workspace API

The initial phase exposes these backend operations under `/api/v1`:

- `POST /auth/signup` — creates a normal customer account.
- `POST /dealerships/register` — creates a dealership, its default
  test-drive settings, and the registering user as `dealership_admin`.
- `POST /dealerships/{id}/staff/invite` — creates a `manager` or `sales_rep`
  account scoped to the dealership with a pending activation record.
- `POST /auth/activate-invitation` — lets the invited staff member set a
  permanent password using the activation token.
- `POST/GET /dealerships/{id}/vehicles` — creates and lists dealership
  vehicles.
- `PUT /dealerships/{id}/test-drive-settings` — configures opening time,
  closing time, slot duration, capacity, and open weekdays.
- `POST /dealerships/{id}/test-drive-slots/generate` — creates missing slots
  for enabled vehicles in a requested date range; repeating the request does
  not duplicate slots.

Email delivery is intentionally isolated from account creation. The current
phase records `email_provider_pending` because no SMTP or external email
provider has been configured yet; it does not expose or log temporary
passwords. The next delivery step should connect the invitation activation
token to the configured email provider.

## 9. Recommended implementation order

The safest vertical slice is:

1. Add migrations and PostgreSQL-compatible models for dealership, roles,
   brands, vehicle variants, and inventory.
2. Add tenant and role authorization to the existing authentication flow.
3. Seed Honda and Toyota catalog data and expose read-only catalog/inventory
   APIs.
4. Add conversations and website chat persistence.
5. Add knowledge retrieval and brand-scoped agent routing.
6. Add lead creation, slot lookup, and transactional test-drive booking.
7. Add signed domain events and n8n confirmation/reminder workflows.
8. Add the staff control center, analytics, evaluation suite, and additional
   channel adapters.

This order follows the project plan's principle that one reliable
`chat -> grounded answer -> inventory -> lead -> booking -> notification`
journey is more valuable than many disconnected features.
