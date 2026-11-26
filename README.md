# DealerDesk

Multi-tenant automotive dealership SaaS combining a **public customer-facing AI showroom & embeddable website widget** (`/`, `/embed/[dealershipId]`) with an **isolated internal dealership CRM** (`/dashboard`, leads, multi-channel inbox, inventory, test-drive scheduling, RAG knowledge base, operations/outbox, staff, and governance).

## Architecture Overview
- **Public Showroom & Embed Widget (`/` & `/embed/[dealershipId]`):** Unauthenticated, zero-CRM-auth surfaces powered by `PublicAgentChat` (`/api/v1/dealerships/{id}/assistant/chat/stream` + `/leads`). See [EMBEDDABLE_AGENT_ARCHITECTURE.md](docs/EMBEDDABLE_AGENT_ARCHITECTURE.md).
- **Internal CRM (`/dashboard`, `/leads`, `/inbox`, `/inventory`, `/bookings`, `/operations`, `/staff`, `/brands`, `/knowledge`, `/audit`, `/dealerships`):** `HttpOnly` cookie JWT authentication with role-based access control (`customer`, `sales_rep`, `manager`, `dealership_admin`, `dealerdesk_admin`).
- **Channel & Automation Endpoints:** `orchestration.py`, `governance.py`, `sales_agent.py`, `/channels/whatsapp`, and `/channels/vapi` provide webhook/automation and governance APIs for external integrations and background dispatchers.

## Running Locally

### 1. Backend (FastAPI + PostgreSQL)
```powershell
cd backend
cp .env.example .env
# Set DATABASE_URL / SUPABASE_CONNECTION_STRING and secrets
uvicorn app.main:app --reload
```
Runs at `http://127.0.0.1:8000` (health check: `GET /api/v1/health`).

### 2. Frontend (Next.js 15)
```powershell
cd frontend
cp .env.example .env.local
npm install
npm run dev
```
Runs at `http://localhost:3000`.

> **Important:** Do not run `npm run build` (`next build`) while `npm run dev` is running in the same directory—stop `npm run dev` first or restart it afterward so `.next` chunks stay in sync.

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
