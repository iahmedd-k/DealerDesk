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