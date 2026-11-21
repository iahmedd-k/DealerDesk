"""Stable demo credentials for local and integration testing."""

import os

CUSTOMER_DEMO_NAME = "DealerDesk Customer Demo"
CUSTOMER_DEMO_EMAIL = "customer-demo@dealerdesk.dev"
CUSTOMER_DEMO_PASSWORD = "DealerDeskCustomer!2026"

DEALERSHIP_DEMO_NAME = "DealerDesk Dealership Demo"
DEALERSHIP_DEMO_EMAIL = "dealership-demo@dealerdesk.dev"
DEALERSHIP_DEMO_PASSWORD = "DealerDeskDealership!2026"
DEALERSHIP_DEMO_BUSINESS_EMAIL = "dealership-demo-business@dealerdesk.dev"

DEALERDESK_ADMIN_DEMO_NAME = os.environ.get(
    "DEALERDESK_ADMIN_NAME", "DealerDesk Admin"
)
DEALERDESK_ADMIN_DEMO_EMAIL = os.environ.get(
    "DEALERDESK_ADMIN_EMAIL", "dealerdesk@demo.com"
)
DEALERDESK_ADMIN_DEMO_PASSWORD = os.environ.get(
    "DEALERDESK_ADMIN_PASSWORD", "adminadmin"
)

# Backwards-compatible aliases for callers using the original demo account.
DEMO_USER_NAME = CUSTOMER_DEMO_NAME
DEMO_USER_EMAIL = CUSTOMER_DEMO_EMAIL
DEMO_USER_PASSWORD = CUSTOMER_DEMO_PASSWORD
