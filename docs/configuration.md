# Configuration

Configuration is loaded by `app/core/config.py` using `pydantic-settings`. Values come from environment variables and, when present, `backend/.env`. Unknown variables are ignored.

```text
backend/.env.example  →  copy to  →  backend/.env
```

## Environment variables

### Required

| Variable | Aliases | Required | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | `SUPABASE_CONNECTION_STRING`, `supabase_string` | Yes | PostgreSQL connection string. Must start with `postgresql://` or `postgresql+`. |
| `JWT_SECRET_KEY` | — | Yes (for auth) | Secret used to sign JWTs. Long, random value. Token operations return `503` when missing. |

The app refuses to initialize if `DATABASE_URL` is not a PostgreSQL URL.

### JWT and sessions

| Variable | Default | Description |
| --- | --- | --- |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime in minutes. |

Refresh tokens have a fixed 30-day lifetime in code.

### Database pool

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_POOL_SIZE` | `5` | Persistent pool connections (≥ 1). |
| `DATABASE_MAX_OVERFLOW` | `10` | Extra connections beyond pool size (≥ 0). |
| `DATABASE_POOL_TIMEOUT` | `30` | Seconds to wait for a connection (≥ 1). |
| `DATABASE_POOL_RECYCLE` | `1800` | Seconds before a connection is recycled (≥ -1). |
| `DATABASE_POOL_PRE_PING` | `true` | Validate connections before use. |
| `DATABASE_SCHEMA` | unset | Optional PostgreSQL schema; sets the connection `search_path`. Used by tests for `dealerdesk_test`. |

### CORS and browser origins

| Variable | Default | Description |
| --- | --- | --- |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated list of allowed browser client origins. |

### Platform administrator seed

| Variable | Default | Description |
| --- | --- | --- |
| `DEALERDESK_ADMIN_EMAIL` | `dealerdesk@demo.com` | Email for the platform superadmin account. |
| `DEALERDESK_ADMIN_PASSWORD` | `adminadmin` | Initial password for the platform superadmin account. |
| `DEALERDESK_ADMIN_NAME` | `DealerDesk Platform Admin` | Display name for the platform superadmin account. |

### Supabase Storage (brand logos and vehicle images)

| Variable | Aliases | Default | Description |
| --- | --- | --- | --- |
| `SUPABASE_URL` | — | unset | Supabase project URL. |
| `SUPABASE_KEY` | `SUPABASE_SECRET_KEY`, `SUPABASE_PUBLISHABLE_KEY` | unset | Supabase API key used by the server. |
| `SUPABASE_BUCKET_ID` | `supabase_bucket_id` | `brand-logos` | Public storage bucket for logos. |
| `VEHICLE_IMAGES_BUCKET_ID` | `vehicle_images_bucket_id` | `vehicle-images` | Public storage bucket for vehicle images. |

If `SUPABASE_URL` or the key is missing, logo/image upload and deletion
endpoints return `503`. Both buckets must exist and be publicly readable for
returned URLs to work. Vehicle image uploads accept JPEG, PNG, and WebP files up
to 10 MB; create the `vehicle-images` bucket in Supabase before uploading.

### Email (Resend)

| Variable | Aliases | Default | Description |
| --- | --- | --- | --- |
| `RESEND_API_KEY` | `resend_api_key` | unset | Resend API key. When unset, email delivery is skipped and status is `email_provider_pending`. |
| `RESEND_FROM_EMAIL` | `RESEND_FROM_EMAIL` | `DealerDesk Support <support@ahmedkhandev.tech>` | Sender identity. |
| `RESEND_REPLY_TO` | `resend_reply_to` | unset | Optional reply-to address. |

### Telephony, WhatsApp & Voice AI (Twilio, Vapi & ngrok)

| Variable | Aliases | Default | Description |
| --- | --- | --- | --- |
| `TWILIO_ACCOUNT_SID` | `twilio_account_sid` | unset | Twilio Account SID found in Twilio Console. |
| `TWILIO_AUTH_TOKEN` | `twilio_auth_token` | unset | Twilio Auth Token for REST API authentication. |
| `TWILIO_WHATSAPP_FROM` | `twilio_whatsapp_from` | `whatsapp:+14155238886` | Twilio WhatsApp sender identifier (use `whatsapp:+14155238886` for Twilio Sandbox). |
| `VAPI_API_KEY` | `vapi_api_key` | unset | Vapi private API key for initiating outbound calls and managing assistants. |
| `VAPI_ASSISTANT_ID` | `vapi_assistant_id` | unset | Default Vapi assistant ID for voice calls. |
| `VAPI_PHONE_NUMBER_ID` | `vapi_phone_number_id` | unset | Vapi phone number ID used for outbound calls. |
| `VAPI_WEBHOOK_SECRET` | `vapi_webhook_secret` | unset | Optional secret validated against the `x-vapi-secret` webhook header. |
| `NGROK_TOKEN` | — | unset | ngrok CLI authtoken for local webhook tunneling. |
| `NGROK_ENDPOINT` | — | unset | Command and reserved domain for ngrok HTTP tunnel. |

### Knowledge embeddings

| Variable | Default | Description |
| --- | --- | --- |
| `EMBEDDING_API_URL` | unset | Optional OpenAI-compatible embeddings endpoint. When unset, a deterministic local hash-embedding provider is used. |
| `EMBEDDING_API_KEY` | unset | Optional bearer token for the embeddings endpoint. |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model identifier sent to the configured endpoint. |

The configured endpoint must accept `POST` requests with `{ "model": "...",
"input": ["..."] }` and return an OpenAI-compatible `data[].embedding` array.
Keep the endpoint/model configuration stable for already-indexed documents; a
model change requires re-uploading documents because embeddings from different
models are not comparable.

## Example `.env`

```dotenv
DATABASE_URL=postgresql+psycopg://dealerdesk:change-me@localhost:5432/dealerdesk
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
DATABASE_POOL_PRE_PING=true
# DATABASE_SCHEMA=

CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

DEALERDESK_ADMIN_EMAIL=dealerdesk@demo.com
DEALERDESK_ADMIN_PASSWORD=adminadmin

SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_BUCKET_ID=brand-logos
VEHICLE_IMAGES_BUCKET_ID=vehicle-images

RESEND_API_KEY=
RESEND_FROM_EMAIL=DealerDesk Support <support@example.com>
RESEND_REPLY_TO=
```

## External services

### PostgreSQL

- The app supports standard PostgreSQL DSNs, including managed providers (e.g., Supabase connection strings via `SUPABASE_CONNECTION_STRING`).
- The startup migration executes PostgreSQL-specific SQL (`ALTER TABLE ... IF NOT EXISTS`, partial indexes, `DO $$` blocks, `ON CONFLICT`). Other database engines are not supported.
- `psycopg[binary]` provides the driver.

### Supabase Storage

- Logos are written to `dealerships/{dealership_id}/brands/{brand_id}/logo`.
- Vehicle images are written to `dealerships/{dealership_id}/vehicles/{vehicle_id}/{uuid}.{jpg|png|webp}`.
- Uploads use `upsert: true`, `cache-control: 3600`, and the file's content type.
- Supported: JPEG, PNG, WebP, ≤ 3 MB. The upload validates magic bytes before sending.
- Vehicle image uploads use `upsert: false`, validate magic bytes, and accept up to 10 MB. The database stores each image's public URL and ordering; deleting an image removes both its storage object and metadata.

### Resend

- Called over HTTPS at `https://api.resend.com/emails` using `urllib`.
- Used for staff invitations and password resets.
- Delivery outcomes: `email_sent`, `email_provider_pending` (no key), `email_delivery_failed`.
- For password resets, a failed/pending delivery deletes the reset token so it cannot be used unseen.

## Test-only variables

| Variable | Purpose |
| --- | --- |
| `TEST_DATABASE_URL` | Optional DSN for the test database. Falls back to `DATABASE_URL`. Tests always use the dedicated `dealerdesk_test` schema and recreate it per test. |

The test suite also injects these environment values at import time: `SUPABASE_CONNECTION_STRING`, `DATABASE_URL`, `DATABASE_SCHEMA=dealerdesk_test`, a fixed `JWT_SECRET_KEY`, and an empty `RESEND_API_KEY`. See [Testing](testing.md).

## Configuration precedence

1. Process environment variables.
2. `backend/.env` file.
3. Field defaults in `Settings`.

`get_settings()` is cached with `lru_cache`; tests call `get_settings.cache_clear()` when they change environment variables.

## Security guidance

- Never commit `backend/.env`; it is ignored by git.
- Keep `.env.example` updated when variables are added.
- Use a 32+ byte random `JWT_SECRET_KEY` and store it in the platform secret manager in production.
- Prefer a least-privilege database role for the application and a separate role for startup migrations if your platform requires it.
- Treat `SUPABASE_KEY` and `RESEND_API_KEY` as secrets.

## Related documents

- [Getting Started](getting-started.md)
- [Deployment](deployment.md)
- [Authentication](authentication.md)
