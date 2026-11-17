from typing import Final


CUSTOMER_ROLE: Final = "customer"
DEALERSHIP_ADMIN_ROLE: Final = "dealership_admin"
MANAGER_ROLE: Final = "manager"
SALES_REP_ROLE: Final = "sales_rep"

STAFF_ROLES: Final = frozenset(
    {DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, SALES_REP_ROLE}
)
DEALERSHIP_MANAGEMENT_ROLES: Final = frozenset(
    {DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE}
)
