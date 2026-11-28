# DealerDesk

Multi-tenant automotive dealership SaaS combining a **public customer-facing AI showroom & embeddable website widget** (`/`, `/embed/[dealershipId]`) with an **isolated internal dealership CRM** (`/dashboard`, leads, multi-channel inbox, inventory, test-drive scheduling, RAG knowledge base, operations/outbox, staff, and governance).

## Architecture Overview
- **Public Showroom & Embed Widget (`/` & `/embed/[dealershipId]`):** Unauthenticated, zero-CRM-auth surfaces powered by `PublicAgentChat` (`/api/v1/dealerships/{id}/sales-agent/...` + `/leads`). See [EMBEDDABLE_AGENT_ARCHITECTURE.md](docs/EMBEDDABLE_AGENT_ARCHITECTURE.md).
- **Internal CRM (`/dashboard`, `/leads`, `/inbox`, `/inventory`, `/bookings`, `/service`, `/operations`, `/staff`, `/brands`, `/knowledge`, `/audit`, `/dealerships`):** `HttpOnly` cookie JWT authentication with role-based access control (`customer`, `sales_rep`, `manager`, `dealership_admin`, `dealerdesk_admin`).
  - **Executive Dashboard (`/dashboard`):** Segmented views (`Overview`, `Pipeline`, `Test Drives`, `Handoffs`), KPI sparklines, pipeline stage chart, lead source mix, and CSV export.
  - **Customer Leads (`/leads`):** KPI summary strip, scannable pipeline table, and slide-over detail/timeline drawer.
  - **Omnichannel Inbox (`/inbox`):** 3-column workspace (`My Inbox` list, active thread with in-thread search & soft-lavender staff/AI bubbles, and right-hand contact/lead details panel).
  - **My Inventory (`/inventory`):** Filter sidebar, `My Cars` list, slide-over `Car Details` drawer with photo gallery management, and full-screen image lightbox.
- **Action-Capable Dealership Assistant (`/assistant`):** Grounded RAG + staff action execution (`dealership_agent_service.py`) supporting natural-language and uploaded `.csv`/`.json`/`.txt` vehicle creation, vehicle status/price updates, test-drive slot creation/generation/updates, booking outcomes (`completed` / `no_show`), and lead updates.
- **Caching & Email Delivery:** Optional Upstash Redis REST caching (`UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`) for inventory/brands/reports/OTP, and Resend email delivery (`RESEND_API_KEY`). For remote pooled PostgreSQL (e.g., Supabase), set `DATABASE_POOL_PRE_PING=false` and `DATABASE_POOL_RECYCLE=300` in `backend/.env` to avoid per-checkout RTT overhead.
- **Channel & Automation Endpoints:** `orchestration.py`, `governance.py`, `sales_agent.py`, `/channels/whatsapp`, and `/channels/vapi` provide webhook/automation and governance APIs for external integrations and background dispatchers.

## Interface Design

The interface design direction adapts spacing, color, typography, and interaction principles from [unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The CRM-specific implementation retains DealerDesk branding and workflows.

## Running Locally

### 1. Backend (FastAPI + PostgreSQL)
```powershell
cd backend
cp .env.example .env
# Set DATABASE_URL / SUPABASE_CONNECTION_STRING and secrets
uvicorn app.main:app --reload
```
Runs at `http://127.0.0.1:8000` (health check: `GET /api/v1/health`).

Run the scheduled CRM jobs in a separate terminal/process:

```powershell
cd backend
python -m app.worker
```

Keep one worker process active per deployment. It polls every 30 seconds to send due test-drive reminders and dispatch outbox events with configured per-event webhook targets. Connected Gmail mailboxes sync automatically about every five minutes, with retry backoff when a provider call fails. The API server does not start duplicate worker loops inside web replicas.

### 2. Frontend (Next.js 15)
```powershell
cd frontend
cp .env.example .env.local
npm install
npm run dev
```
Runs at `http://localhost:3000`.

> **Important:** Do not run `npm run build` (`next build`) while `npm run dev` is running in the same directory—stop `npm run dev` first or restart it afterward so `.next` chunks stay in sync.

### Google Workspace Inbox

The CRM Inbox can connect one shared Google Workspace/Gmail mailbox per dealership. Gmail is an optional integration; Resend remains responsible for DealerDesk verification and notification emails.

1. In Google Cloud Console, enable the Gmail API and create an OAuth client ID for a **Web application**.
2. Add the exact value of `GOOGLE_OAUTH_REDIRECT_URI` as an authorized redirect URI. The local example is `http://localhost:8000/api/v1/email/google/callback`.
3. Configure the OAuth consent screen and add dealership mailboxes as test users while the Google app is in testing. Production use of Gmail scopes requires Google’s app verification.
4. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, and `FRONTEND_BASE_URL` in `backend/.env`. Generate `GMAIL_TOKEN_ENCRYPTION_KEY` with:

   ```powershell
   python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

   Keep this key in your secret manager and stable across deployments; it encrypts Gmail refresh tokens stored in the database.
5. In DealerDesk, open **Settings → Shared Gmail inbox** and connect the dealership’s shared account. The first sync imports up to 50 recent inbox threads; subsequent changes sync automatically, and **Sync email** remains available for a manual refresh. Replies are sent from the connected mailbox. Attachment metadata is shown in the thread and downloads are proxied through the authenticated CRM API.

## CRM Workflow Notes

- The lead board supports bulk status/assignment actions and CSV import/export. Lead exports include loss reasons and structured deal, trade-in, and financing terms. Lead CSV imports require `name`, `email`, `message`, and `consent_to_contact` headers; vehicle imports require `brand_id`, `model`, `model_year`, `price`, and `stock_number`. Vehicle imports show a validated create/update preview before applying upserts and accept optional acquisition cost, location, reconditioning status, acquisition date, and vehicle specs. Imports accept up to 500 rows (2 MB) and return row-level validation errors.
- Lost leads can record structured close-out reasons; these reasons are shown in the lead editor and included in transition-date analytics.
- Lead follow-up actions open the user's configured email, SMS, or WhatsApp app. They do not send through DealerDesk; the user reviews and sends the message externally. The matching channel-specific permission is required, and grants/opt-outs are timestamped in the lead activity timeline.
- Deal terms, trade-in values, and financing inputs are saved with the lead. Each saved quote creates an immutable, numbered version with a status lifecycle and a matching activity timeline entry; estimates can be printed or drafted into email and exclude taxes, fees, and lender approval.
- Dashboard pipeline and source-mix cards use full-dataset server aggregates rather than the recent-lead preview. Source conversion and the current-owner rep cohort are scoped to leads created within the selected dates and use current status. Historical charts use activity dates; closed-won credit uses the assignee and deal value captured at the status change (older events without that metadata remain unattributed). The notification center refreshes active overdue follow-ups, assigned inbox handoffs, and upcoming test drives every 30 seconds while the app is visible.
- Vehicle VIN decoding uses the public NHTSA vPIC API. A VIN submitted for decoding is sent to that provider.
- The After-sales workspace tracks service appointments, work-order status and costs, vehicle warranty terms, and due/completed customer follow-ups. Its records are dealership-scoped and available to staff roles.

## Seeded Demo Credentials
Defined in `backend/seed/demo_credentials.py`:
- **Customer:** `customer-demo@dealerdesk.dev` / `DealerDeskCustomer!2026`
- **Dealership Admin:** `dealership-demo@dealerdesk.dev` / `DealerDeskDealership!2026`
- **Platform SuperAdmin (`dealerdesk_admin`):** `dealerdesk@demo.com` / `adminadmin` (must be overridden via `DEALERDESK_ADMIN_PASSWORD` when `ENVIRONMENT=production`)

## Verification Commands
```powershell
# Frontend typecheck & production build
cd frontend
npx tsc --noEmit --incremental false
npm run build
```
