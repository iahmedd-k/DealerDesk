# DealerDesk Public Landing Page & Multi-Dealership Embed Architecture

## 1. Separation Between Public Showroom & Core CRM

DealerDesk cleanly separates **public customer-facing entrypoints** from the **authenticated internal CRM**:

| Surface | Route | Auth Required | Purpose |
|---|---|---|---|
| **Public Landing Page** | `/` (`frontend/app/page.tsx`) | No | B2B SaaS showcase + live interactive Agentic Customer Chatbot + public inventory preview. |
| **Embeddable Chat Widget** | `/embed/[dealershipId]` (`frontend/app/embed/[dealershipId]/page.tsx`) | No | Zero-chrome chat widget designed to run inside an `<iframe>` on any third-party dealership website. |
| **CRM Workspace** | `/dashboard`, `/leads`, `/inbox`, `/inventory`, `/bookings`, `/operations`, `/staff`, `/brands`, `/knowledge`, `/audit`, `/dealerships` | Yes (`HttpOnly` JWT cookie) | Internal dealership & platform administration workspace wrapped in `<Shell>`. |

### Auth Isolation
In `frontend/app/providers.tsx`, `AuthProvider` detects public routes (`pathname === "/" || pathname.startsWith("/embed")`) and skips `/auth/me` and `/auth/refresh` session-restore calls. Anonymous website visitors never trigger `401 Unauthorized` noise or login redirects.

---

## 2. Multi-Dealership Integration: Existing Websites vs. Hosted Landing Page

When selling DealerDesk to multiple dealerships:

1. **Dealership already has their own website (WordPress, Dealer.com, Webflow, custom site):**
   - They keep their existing website untouched and paste the 1-line `<iframe>` snippet pointing to `/embed/{dealership_id}`.
   - All chat messages stream via `POST /api/v1/dealerships/{dealership_id}/assistant/chat/stream` with `channel: "website"`.
   - Any lead capture / "Talk to Sales" submission posts to `POST /api/v1/dealerships/{dealership_id}/leads` and lands directly in that dealership's CRM `/leads` and `/inbox`.

2. **Dealership has no website / wants a hosted showroom:**
   - The same `PublicAgentChat` component powers `/` (with tenant selector) and can be routed per dealership.

---

## 3. Edge Cases & Mitigations

1. **CSS & JavaScript Conflicts on External Dealer Sites**
   - *Risk:* Injecting raw React/CSS bundles into a dealership's WordPress/Dealer.com DOM causes style collisions.
   - *Mitigation:* Hosting `/embed/[dealershipId]` inside an `<iframe>` guarantees complete DOM, CSS, and JS isolation.

2. **Cross-Origin (CORS) Blocking from Hundreds of Dealer Domains**
   - *Risk:* Calling the FastAPI backend directly from `https://dealer-a.com`, `https://dealer-b.com`, etc. requires maintaining dynamic CORS origin allowlists.
   - *Mitigation:* Because the `<iframe>` is served from DealerDesk's own frontend origin, `fetch` calls to the backend originate from DealerDesk's origin—no per-dealership CORS updates required.

3. **Frame Embedding Headers (`X-Frame-Options` / CSP `frame-ancestors`)**
   - *Risk:* Default `X-Frame-Options: SAMEORIGIN` or strict `frame-ancestors 'self'` headers in reverse proxies (Nginx/Cloudflare/Vercel) will block third-party sites from rendering `/embed/[dealershipId]`.
   - *Mitigation:* Configure `/embed/*` responses with `Content-Security-Policy: frame-ancestors *` (or a per-tenant domain allowlist) and omit `X-Frame-Options: DENY/SAMEORIGIN` on `/embed/*` only, while keeping `SAMEORIGIN` on all CRM routes (`/dashboard`, `/leads`, etc.).

4. **Tenant Isolation & Suspended Subscriptions**
   - *Risk:* A cancelled/suspended dealership still has the `<iframe>` live on their website.
   - *Mitigation:* `assistant_service.validate_assistant_scope` on the backend validates dealership existence and active state on every chat request.

5. **Minimized Floating Launcher & Visitor Session Continuity**
   - *UX:* `/embed/[dealershipId]` defaults to a minimized bottom-right floating launcher (`"Showroom AI"`), matching Azure/Oracle support widgets so it never obscures the dealership's website.
   - *Continuity:* Refreshing the dealership webpage preserves the shopper's identity and conversation via `dealerdesk_visitor_{dealershipId}` and `dealerdesk_chat_history_{dealershipId}` in `localStorage`.

6. **Dealership Verification Without Exposing CRM Credentials**
   - *Risk:* Asking for CRM admin credentials inside a public website widget would expose staff login forms to anonymous car shoppers.
   - *Mitigation:* `/embed/[dealershipId]` verifies the dealership against active `GET /dealerships/public` tenants. If unregistered or suspended, it renders an activation card linking to `/login` and `/signup` in a new tab. Active dealerships copy their scoped `<iframe>` snippet directly from CRM **Operations & Outbox**.

6. **Rate Limiting & Abuse Protection**
   - *Risk:* Public unauthenticated endpoints can be spammed by bots.
   - *Mitigation:* Backend `/assistant/chat/stream` and `/assistant/chat` enforce `@limiter.limit(...)` and PII/prompt-injection guardrails, while lead submission requires explicit `consent_to_contact: true`.
