# API Reference

Base URL: `http://127.0.0.1:8000`

All application endpoints are versioned under `/api/v1`. Interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.

## Conventions

- **Content type:** `application/json`, except logo upload (`multipart/form-data`).
- **Authentication:** `Authorization: Bearer <access_token>` for protected endpoints.
- **Errors:** FastAPI default shape `{ "detail": "message" }`.
- **Collections:** endpoints return JSON arrays without pagination or envelopes.
- **Dealership scoping:** `{dealership_id}` must match the caller's assigned dealership; otherwise `404`.
- **Timestamps:** ISO 8601. Slot times are stored and returned in UTC.

### Authorization legend

| Symbol | Meaning |
| --- | --- |
| Public | No token required |
| Bearer | Any authenticated active user |
| Member | Authenticated user belonging to the dealership |
| Admin | `dealership_admin` in the dealership |
| Admin/Manager | `dealership_admin` or `manager` |
| Staff | `dealership_admin`, `manager`, or `sales_rep` |
| Customer | `customer` role |

## System

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | Public | API status: `{ "message": "DealerDesk backend is running" }` |
| GET | `/api/v1/health` | Public | Health: `{ "status": "ok" }` |

## Authentication

Prefix: `/api/v1/auth`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/signup` | Public | Create a customer account |
| POST | `/login` | Public | Issue access and refresh tokens |
| POST | `/logout` | Bearer | Revoke current access token and all refresh tokens |
| GET | `/me` | Bearer | Current user profile |
| PATCH | `/me` | Bearer | Update name and/or email |
| DELETE | `/me` | Bearer | Soft-deactivate current account |
| GET | `/users` | Admin | List users in the admin's dealership |
| POST | `/refresh` | Public | Rotate a refresh token |
| POST | `/request-password-reset` | Public | Request a reset token by email |
| POST | `/reset-password` | Public | Complete a password reset |
| POST | `/activate-invitation` | Public | Activate an invited staff account |
| POST | `/change-password` | Bearer | Change the current password |

### POST `/auth/signup`

```json
{ "name": "Ahmed Khan", "email": "ahmed@example.com", "password": "strong-password-123" }
```

- `201` → `UserResponse` with `role: "customer"`.
- `409` if the email is already registered.
- `422` on validation failure.

### POST `/auth/login`

```json
{ "email": "ahmed@example.com", "password": "strong-password-123" }
```

`200`:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "refresh_token": "<random-token>"
}
```

`401` for invalid credentials; `503` if JWT configuration is missing.

### POST `/auth/logout`

Requires a valid bearer token. Returns `204`. The token cannot be reused and all refresh tokens for the user are revoked.

### GET `/auth/me`

Returns the authenticated `UserResponse`.

### PATCH `/auth/me`

```json
{ "name": "New Name", "email": "new@example.com" }
```

Fields are optional. `409` if the new email belongs to another account.

### DELETE `/auth/me`

Soft-deactivates the account and revokes sessions. Returns `204`. A dealership admin who is the last active admin receives `409`.

### GET `/auth/users`

Admin-only. Returns all users whose `dealership_id` matches the admin's dealership, ordered by id.

### POST `/auth/refresh`

```json
{ "refresh_token": "<token>" }
```

- `200` → new `TokenResponse`; the supplied token is revoked.
- `401` if the token is unknown, revoked, expired, or the user is inactive.

### POST `/auth/request-password-reset`

```json
{ "email": "ahmed@example.com" }
```

Always returns `200` with a generic message to avoid account enumeration. If the account exists and email delivery succeeds, a one-hour reset token is stored and emailed.

### POST `/auth/reset-password`

```json
{ "token": "<reset-token>", "new_password": "new-password-123" }
```

`200` on success; `400` for an invalid/expired token or unavailable account. All sessions are revoked.

### POST `/auth/activate-invitation`

```json
{ "token": "<activation-token>", "password": "new-password-123" }
```

`200` → `UserResponse`; `400` for an invalid/expired invitation.

### POST `/auth/change-password`

```json
{ "current_password": "old-password", "new_password": "new-password" }
```

`200` → `UserResponse`; `400` if the current password is wrong; `422` if the new password equals the current one.

## Dealerships

Prefix: `/api/v1/dealerships`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `` | Public | List active dealerships |
| GET | `/{dealership_id}` | Public | Get an active dealership |
| POST | `/register` | Public | Register a dealership and its first admin |
| PATCH | `/{dealership_id}` | Admin | Update dealership profile/timezone |
| DELETE | `/{dealership_id}` | Admin | Soft-deactivate the dealership |

### POST `/dealerships/register`

```json
{
  "dealership_name": "Acme Motors",
  "dealership_email": "sales@acme.example",
  "dealership_phone": "555-0100",
  "dealership_address": "1 Main St",
  "timezone": "America/New_York",
  "brands": ["Toyota", "Honda"],
  "admin_name": "Acme Admin",
  "admin_email": "admin@acme.example",
  "admin_password": "Password!123"
}
```

- `brands` must contain 1–20 unique names (trimmed, case-insensitive).
- `timezone` must be a valid IANA zone.
- `201` → `UserResponse` for the created admin.
- `409` if the admin email already exists or registration conflicts.

Registration creates, in one transaction: the dealership, its brands, the admin user, and default test-drive settings.

### PATCH `/dealerships/{dealership_id}`

Accepts `name`, `email`, `phone`, `address`, `timezone`. Admin of the same dealership only. Returns `DealershipResponse`.

## Brands

Prefix: `/api/v1/dealerships/{dealership_id}/brands`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `` | Member | List brands |
| POST | `` | Admin/Manager | Create a brand (max 20 non-deleted) |
| GET | `/{brand_id}` | Member | Get a brand |
| PATCH | `/{brand_id}` | Admin/Manager | Rename and/or activate/deactivate |
| DELETE | `/{brand_id}` | Admin/Manager | Soft-delete (archive) a brand |
| POST | `/{brand_id}/restore` | Admin/Manager | Restore an archived brand (inactive) |
| PUT | `/{brand_id}/logo` | Admin/Manager | Upload a logo (`multipart/form-data`, field `file`) |
| DELETE | `/{brand_id}/logo` | Admin/Manager | Remove the logo |

Query parameters for `GET`:

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `include_inactive` | bool | `false` | Admin/Manager only |
| `include_deleted` | bool | `false` | Admin/Manager only |

Rules:

- Brand names are unique per dealership ignoring case, among non-deleted brands.
- At most 20 non-deleted brands per dealership (`409` when exceeded).
- Deactivating/deleting a brand deactivates its vehicles' future test-drive slots.
- Renaming a brand updates the `make` field of its vehicles.
- Restoring a brand sets `is_deleted=false` and `is_active=false`.
- Logos must be JPEG, PNG, or WebP, ≤ 3 MB, with a matching file signature. Requires Supabase configuration (`503` otherwise).
- Errors: `404` not found, `409` duplicate/limit, `413` too large, `415` unsupported type, `422` bad signature.

## Vehicles

Prefix: `/api/v1/dealerships/{dealership_id}/vehicles`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `` | Staff | Create a vehicle |
| GET | `` | Member | List vehicles |
| GET | `/{vehicle_id}` | Member | Get a vehicle |
| PATCH | `/{vehicle_id}` | Staff | Update a vehicle |
| DELETE | `/{vehicle_id}` | Admin/Manager | Soft-delete a vehicle |
| PATCH | `/{vehicle_id}/availability?available=true` | Staff | Toggle availability |

Query parameter for `GET`: `include_archived_brands` (bool, default `false`, Admin/Manager only). By default, listings exclude vehicles whose brand is inactive or deleted.

### Create request

```json
{
  "brand_id": 3,
  "model": "Camry",
  "model_year": 2026,
  "variant": "LE",
  "description": "Demo vehicle",
  "price": 28900,
  "stock_number": "ACME-0001",
  "test_drive_enabled": true
}
```

- `brand_id` must reference an active, non-deleted brand in the same dealership (`422` otherwise).
- `stock_number` must be unique per dealership (`409`).
- `make` is derived from the brand name.

### Update request

All fields optional: `brand_id`, `model`, `model_year`, `variant`, `description`, `price`, `stock_number`, `is_available`, `test_drive_enabled`. Setting `is_available=true` or `test_drive_enabled=true` is rejected with `409` if the brand is inactive/deleted.

## Staff

Prefix: `/api/v1/dealerships/{dealership_id}/staff`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `` | Admin/Manager | List staff (non-customers) |
| POST | `/invite` | Admin | Invite a manager or sales rep |
| GET | `/invitations` | Admin/Manager | List invitations |
| DELETE | `/invitations/{invitation_id}` | Admin | Revoke a pending invitation |
| GET | `/{user_id}` | Admin/Manager | Get a staff member |
| PATCH | `/{user_id}` | Admin | Update name, role, or active status |
| DELETE | `/{user_id}` | Admin | Remove (deactivate) a staff member |

### POST `/staff/invite`

```json
{ "name": "Sam Sales", "email": "sam@acme.example", "role": "sales_rep" }
```

- Allowed roles: `manager`, `sales_rep`.
- `201` → `StaffInvitationResponse` including `delivery_status`.
- `409` if the email belongs to a customer, another dealership, or an already-active invited account.
- Re-inviting a pending/revoked/expired staff account rotates the activation token and invalidates old sessions.

### PATCH `/staff/{user_id}`

```json
{ "name": "Sam Updated", "role": "manager", "is_active": true }
```

- `409` if changing the role or deactivating the last active admin.
- Deactivation revokes sessions.

### DELETE `/staff/{user_id}`

Deactivates the staff member. `400` if an admin attempts to remove themselves; `409` if it would remove the last active admin.

## Test Drives

Prefix: `/api/v1/dealerships/{dealership_id}`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/test-drive-settings` | Public | Get scheduling settings |
| PUT | `/test-drive-settings` | Admin | Create/update settings |
| DELETE | `/test-drive-settings` | Admin | Delete settings and deactivate future slots |
| POST | `/test-drive-slots/generate` | Admin | Generate slots for a date range |
| GET | `/test-drive-slots` | Public | List slots |
| GET | `/test-drive-slots/{slot_id}` | Public | Get a slot |
| PATCH | `/test-drive-slots/{slot_id}` | Admin | Activate/deactivate a slot |
| DELETE | `/test-drive-slots/{slot_id}` | Admin | Deactivate a slot |
| GET | `/test-drive-slots/{slot_id}/bookings` | Bearer | List bookings for a slot |
| GET | `/test-drive-bookings` | Customer | List the caller's bookings |
| POST | `/test-drive-slots/{slot_id}/bookings` | Customer | Book a slot |
| DELETE | `/test-drive-bookings/{booking_id}` | Customer/Staff | Cancel a booking |

### PUT `/test-drive-settings`

```json
{
  "opening_time": "09:00",
  "closing_time": "17:00",
  "slot_duration_minutes": 30,
  "capacity_per_slot": 1,
  "days_open": [0, 1, 2, 3, 4]
}
```

- `days_open` uses ISO weekdays (0 = Monday … 6 = Sunday); values are sorted and de-duplicated by validation.
- `slot_duration_minutes` is 15–240; `capacity_per_slot` is 1–100.
- Opening must be before closing (`422`).
- Updating settings reconciles **future** slots: removed times are deactivated, remaining slots are extended/capacity-adjusted, and new expected slots are created. Capacity never drops below the current booked count.

### POST `/test-drive-slots/generate?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

- Range must be 0–90 days.
- Requires existing settings (`422` otherwise).
- Creates slots only on open weekdays, for vehicles that are available, test-drive-enabled, and belong to an active/non-deleted brand.
- Times are interpreted in the dealership timezone and converted to UTC; non-existent DST wall-clock times are skipped.
- Returns the newly created slots. Existing `(dealership, vehicle, starts_at)` slots are not duplicated.

### GET `/test-drive-slots`

Query: `include_inactive` (bool, default `false`). Returns slots ordered by `starts_at`.

### PATCH `/test-drive-slots/{slot_id}`

```json
{ "is_active": true }
```

`409` if attempting to deactivate a slot with existing bookings.

### DELETE `/test-drive-slots/{slot_id}`

Soft-deactivates the slot. `409` if it has bookings.

### POST `/test-drive-slots/{slot_id}/bookings`

Customer only. Requires `201`. Rejected with `409` when:

- The slot is inactive, in the past, or full.
- The vehicle is unavailable, not test-drive enabled, or its brand is inactive/deleted.
- The customer already has an active booking for the slot.

The slot's `booked_count` is incremented atomically under a row lock.

### GET `/test-drive-slots/{slot_id}/bookings`

- Customers see only their own bookings for the slot.
- Dealership staff see all bookings for the slot.
- Users outside the dealership receive `404`.

### GET `/test-drive-bookings`

Customer only; returns the caller's bookings for the dealership, newest first.

### DELETE `/test-drive-bookings/{booking_id}`

Cancels an active booking and decrements the slot's booked count. Customers may cancel only their own bookings; staff may cancel bookings in their dealership. Returns `204`.

## Response schemas

### `UserResponse`

```json
{
  "id": 1,
  "name": "Ahmed Khan",
  "email": "ahmed@example.com",
  "role": "customer",
  "dealership_id": null,
  "must_change_password": false
}
```

### `DealershipResponse`

```json
{
  "id": 1,
  "name": "Acme Motors",
  "email": "sales@acme.example",
  "phone": "555-0100",
  "address": "1 Main St",
  "timezone": "America/New_York",
  "is_active": true
}
```

### `BrandResponse`

```json
{
  "id": 3,
  "dealership_id": 1,
  "name": "Toyota",
  "logo_url": "https://.../logo",
  "is_active": true,
  "is_deleted": false
}
```

### `VehicleResponse`

```json
{
  "id": 10,
  "dealership_id": 1,
  "brand_id": 3,
  "make": "Toyota",
  "model": "Camry",
  "model_year": 2026,
  "variant": "LE",
  "description": "Demo vehicle",
  "price": 28900,
  "stock_number": "ACME-0001",
  "test_drive_enabled": true,
  "is_available": true
}
```

### `StaffInvitationResponse`

```json
{
  "id": 5,
  "user_id": 12,
  "email": "sam@acme.example",
  "role": "sales_rep",
  "expires_at": "2026-11-18T12:00:00Z",
  "delivery_status": "email_sent",
  "status": "pending"
}
```

### `TestDriveSettingsResponse`

```json
{
  "id": 1,
  "dealership_id": 1,
  "opening_time": "09:00",
  "closing_time": "17:00",
  "slot_duration_minutes": 30,
  "capacity_per_slot": 1,
  "days_open": [0, 1, 2, 3, 4]
}
```

### `TestDriveSlotResponse`

```json
{
  "id": 77,
  "vehicle_id": 10,
  "starts_at": "2026-11-17T14:00:00Z",
  "ends_at": "2026-11-17T14:30:00Z",
  "capacity": 1,
  "booked_count": 0,
  "is_active": true
}
```

### `TestDriveBookingResponse`

```json
{
  "id": 21,
  "slot_id": 77,
  "dealership_id": 1,
  "vehicle_id": 10,
  "customer_id": 1,
  "status": "booked",
  "created_at": "2026-11-16T12:00:00Z",
  "cancelled_at": null
}
```

## Related documents

- [Authentication](authentication.md)
- [Data Model](data-model.md)
- [Configuration](configuration.md)
- [Roadmap & Limitations](roadmap.md)
