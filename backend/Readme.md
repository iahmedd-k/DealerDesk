## Demo credentials

Seed the shared demo account against the database configured in `backend/.env`:

```powershell
cd backend
python -m seed.seed_demo_user
```

The command is idempotent and refreshes both account passwords when they already
exist. Use these credentials for local and integration testing only:

- Customer email: `customer-demo@dealerdesk.dev`
- Customer password: `DealerDeskCustomer!2026`
- Dealership admin email: `dealership-demo@dealerdesk.dev`
- Dealership admin password: `DealerDeskDealership!2026`

Do not use this account in production or expose it outside test environments.

## Running backend tests

The integration tests drop and recreate the `dealerdesk_test` schema. They use
`TEST_DATABASE_URL` when set, or the PostgreSQL database configured in `.env`
otherwise. In either case, tests are restricted to the dedicated
`dealerdesk_test` schema; do not store application data in that schema.

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/dealerdesk_test"
pytest
```

## Dealership brands

Dealership registration requires a `brands` array containing 1-20 unique brand
names. Brand names are unique per dealership without regard to letter case.
Vehicles require a `brand_id` belonging to an active brand in the same
dealership; the brand's name is returned as the vehicle's legacy `make` field.

Dealership admins and managers can list, add, rename, deactivate, archive, and
restore brands through `/api/v1/dealerships/{dealership_id}/brands`. Inactive
brands remain associated with historical vehicles and bookings, but are
excluded from inventory and test-drive availability. Archiving is a soft delete;
restored brands start inactive, and vehicle availability is not changed.

Brand logos are optional JPEG, PNG, or WebP uploads (up to 3 MB) stored in a
public Supabase Storage bucket. Configure `SUPABASE_URL`, `SUPABASE_KEY`, and
`SUPABASE_BUCKET_ID`; create the bucket before uploading logos.