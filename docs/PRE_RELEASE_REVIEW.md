# DealerDesk Pre-Release QA & Product Review

**Review Status:** Phase 1 Complete → Phase 2 In Progress  
**Constraint:** Audit & report only (no product code modifications unless explicitly requested).

---

## Phase 1: Discovery (Completed)

### 1. Project Context
- **Project Name & Purpose:** **DealerDesk** — multi-tenant automotive dealership SaaS combining a public customer-facing AI showroom & embeddable website agent (`/`, `/embed/[dealershipId]`) with an isolated internal dealership CRM (`/dashboard`, leads, multi-channel inbox, inventory, test-drive scheduling, RAG knowledge base, operations/outbox, staff, and governance).
- **Tech Stack:**
  - **Frontend:** Next.js 15 (`15.5.29`, App Router, TypeScript, Tailwind CSS) in `frontend/`
  - **Backend:** FastAPI + SQLAlchemy + Alembic + SlowAPI rate limiter in `backend/`
  - **Database:** PostgreSQL (`psycopg2`)
  - **Auth:** JWT access + refresh tokens via `HttpOnly` cookies (`credentials: "include"`), token revocation/versioning, email verification, password reset, and account lockout
  - **Channels / AI:** SSE streaming AI assistant (`assistant.py`, `sales_agent.py`), RAG knowledge chunks, WhatsApp & Vapi Voice webhook routers
- **Repo Path:** `d:\Ahmed Dev\Projects\DealerDesk`
- **Seeded Demo Credentials** (`backend/seed/demo_credentials.py`):
  - **Customer:** `customer-demo@dealerdesk.dev` / `DealerDeskCustomer!2026`
  - **Dealership Staff/Admin:** `dealership-demo@dealerdesk.dev` / `DealerDeskDealership!2026`
  - **Platform SuperAdmin (`dealerdesk_admin`):** `dealerdesk@demo.com` / `adminadmin`
- **User Roles:** `guest`, `customer`, `sales_rep`, `manager`, `dealership_admin`, `dealerdesk_admin`

### 2. Feature Inventory
| Feature | Frontend Pages / Components | Backend Endpoints | DB Tables | Allowed Roles |
|---|---|---|---|---|
| Public Landing & Embed Widget | `/`, `/embed/[dealershipId]`, `PublicAgentChat.tsx` | `/dealerships/public`, `/vehicles/public`, `/assistant/chat/stream`, `/leads` | `dealerships`, `vehicles`, `customer_leads`, `audit_logs` | `guest`, all authenticated |
| Authentication & Session | `/login`, `/signup`, `providers.tsx`, `Shell.tsx` | `/auth/*` | `users`, `refresh_tokens`, `revoked_access_tokens`, `user_token_versions`, `email_verification_tokens`, `password_reset_tokens` | `guest`, all authenticated |
| Role-Aware CRM Dashboard | `/dashboard` | `/health`, `/reports/summary`, `/vehicles`, `/leads`, `/test-drive-bookings`, `/conversations` | `dealerships`, `vehicles`, `customer_leads`, `test_drive_bookings`, `conversations` | `customer`, `sales_rep`, `manager`, `dealership_admin`, `dealerdesk_admin` |
| Lead Pipeline & Activities | `/leads` | `/dealerships/{id}/leads*` | `customer_leads`, `lead_activities`, `outbox_events` | `sales_rep`, `manager`, `dealership_admin` (+ public `POST`) |
| Multi-Channel Inbox & Handoff | `/inbox` | `/dealerships/{id}/conversations*`, `/channels/whatsapp/*`, `/channels/vapi/*`, `/dealerships/{id}/channels*` | `conversations`, `conversation_messages`, `otp_verifications` | `sales_rep`, `manager`, `dealership_admin` |
| Vehicle Inventory & Media | `/inventory` | `/dealerships/{id}/vehicles*` | `vehicles`, `vehicle_images`, `vehicle_status_history` | `customer` (read), `sales_rep`, `manager`, `dealership_admin` |
| Test-Drive Slots & Bookings | `/bookings` | `/dealerships/{id}/test-drive-slots*`, `/test-drive-bookings*` | `test_drive_slots`, `test_drive_bookings`, `test_drive_slot_holds`, `notification_deliveries` | `customer`, `sales_rep`, `manager`, `dealership_admin` |
| Brand Portfolio | `/brands` | `/dealerships/{id}/brands*` | `brands` | `manager`, `dealership_admin` |
| AI Copilot (Internal CRM) | `/assistant`, `FormattedMessage.tsx` | `/dealerships/{id}/assistant/chat*`, `/sales-agent*` | `vehicles`, `test_drive_slots`, `knowledge_chunks`, `audit_logs` | All authenticated |
| Knowledge Base (RAG) | `/knowledge` | `/dealerships/{id}/knowledge/*` | `knowledge_documents`, `knowledge_chunks` | `sales_rep`, `manager`, `dealership_admin` |
| Operations, Reminders & Outbox | `/operations` | `/reports/summary`, `/test-drive-settings`, `/test-drive-slots/generate`, `/outbox*`, `/notifications*` | `test_drive_settings`, `outbox_events`, `notification_deliveries`, `idempotency_keys` | `manager`, `dealership_admin` |
| Team, Invites & Availability | `/staff` | `/dealerships/{id}/staff*` | `users`, `staff_invitations` | `sales_rep` (self availability), `manager`, `dealership_admin` |
| Audit Logs & Retention | `/audit` | `/dealerships/{id}/audit-logs`, `/governance/*` | `audit_logs` | `manager`, `dealership_admin`, `dealerdesk_admin` |
| SaaS Tenant Control Tower | `/dealerships` | `/dealerships`, `/dealerships/metrics`, `/dealerships/register`, `/dealerships/{id}/subscription`, `/dealerships/maintenance/retention` | `dealerships`, `users`, `brands`, `vehicles` | `dealerdesk_admin` |

### 3. User Flow Map
1. **Guest / Shopper Flow:** `/` or `/embed/{id}` → stream AI chat → persist visitor session → **Talk to Sales** (`POST /leads`).
2. **Customer Flow:** `/signup` or `/login` (`customer-demo@dealerdesk.dev`) → `/dashboard` → `/inventory` → `/bookings` (book/reschedule/cancel) → `/assistant` → logout.
3. **Dealership Staff / Admin Flow:** `/login` (`dealership-demo@dealerdesk.dev`) → `/dashboard` → `/leads` → `/inbox` → `/inventory` → `/operations` → `/staff` → `/brands`, `/knowledge`, `/audit` → logout.
4. **Platform SuperAdmin Flow:** `/login` (`dealerdesk@demo.com`) → `/dealerships` → `/audit` → logout.

### 4. Unclear / Undocumented Items & Assumptions
1. No root `README.md` exists (`backend/.env.example` and `frontend/.env.example` exist).
2. Live testing in Phase 2 depends on whether PostgreSQL, FastAPI (`127.0.0.1:8000`), and Next.js (`localhost:3000`) are running locally; unrun external integrations (WhatsApp/Vapi webhooks, SMTP) will be labeled `code-review only, unverified`.
3. `orchestration.py`, `governance.py`, and `sales_agent.py` exist in the backend router; Phase 2 will verify their UI/role coverage.

---

## Phase 2: Feature-by-Feature Audit (Tracking)
- [ ] Live Environment & Seeded Auth Check
- [ ] Feature 1: Public Landing & Embed Widget
- [ ] Feature 2: Authentication & Session
- [ ] Feature 3: Role-Aware CRM Dashboard
- [ ] Feature 4: Lead Pipeline & Activities
- [ ] Feature 5: Multi-Channel Inbox & Handoff
- [ ] Feature 6: Vehicle Inventory & Media
- [ ] Feature 7: Test-Drive Slots & Bookings
- [ ] Feature 8: Brand Portfolio
- [ ] Feature 9: AI Copilot (Internal CRM)
- [ ] Feature 10: Knowledge Base (RAG)
- [ ] Feature 11: Operations, Reminders & Outbox
- [ ] Feature 12: Team, Invites & Availability
- [ ] Feature 13: Audit Logs & Governance
- [ ] Feature 14: SaaS Tenant Control Tower

---

## Phase 3: Final Report (Pending Phase 2)
