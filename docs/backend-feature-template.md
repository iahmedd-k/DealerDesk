# Backend Feature Template

Use this guide when adding a backend domain or feature. Adapt the file list to
the feature: do not create empty layers or files that the feature does not need.
Follow the existing implementations and shared helpers before introducing new
patterns.

## 1. Define the feature

Before coding, record:

- **Purpose and users:** What need does this feature address?
- **API contract:** Routes, methods, request/response schemas, status codes, and
  pagination behavior.
- **Authorization:** Required role or permission, resource ownership, and
  dealership/tenant scope for every operation.
- **Business invariants:** Constraints that must remain true, including
  concurrent and retry behavior.
- **Persistence and integrations:** Models, migration needs, and external
  systems involved.
- **Failure behavior:** Expected validation, not-found, conflict, unavailable,
  and unexpected-error behavior.
- **Tests:** Service/domain cases, API authorization cases, and persistence or
  integration cases.

## 2. Choose the smallest appropriate file set

For a persistent API feature, the usual layout is:

```text
backend/app/
├── api/v1/endpoints/<domain>.py       # HTTP routing and dependency wiring
├── schemas/<domain>.py               # Request and response contracts
├── services/<domain>_service.py      # Business rules and orchestration
├── repositories/<domain>_repository.py # Persistence queries and writes
├── models/<domain>.py                # SQLAlchemy mappings, if needed
├── dependencies/                      # Shared auth/policy dependencies, if needed
└── core/                              # Cross-domain configuration/errors, if needed
backend/tests/
├── test_<domain>_service.py          # Business behavior, if service logic warrants it
└── test_<domain>_api.py              # HTTP contract and access-control behavior
```

Not every feature needs every file. For example, a read-only external integration
may need an adapter instead of a repository; a feature with no persistence does
not need a model or repository.

## 3. Keep the dependency direction

```text
HTTP client
    ↓
endpoint → shared auth/authorization dependency
    ↓
schema-validated service operation
    ↓
repository → SQLAlchemy model → database
```

- **Endpoint:** Defines HTTP method/path, request/response schema, status code,
  and dependency wiring. It delegates the operation and does not contain
  business rules or database queries.
- **Schema:** Validates and serializes API input/output. Keep API contracts
  separate from database models; whitelist mutable fields.
- **Service:** Owns domain decisions and multi-step orchestration. It should not
  import endpoint modules or depend on FastAPI request/response objects.
- **Repository:** Owns SQL/ORM access and persistence operations. It should not
  implement workflows or depend on services/API schemas.
- **Model:** Describes persistence state and database constraints. Use a new
  migration for schema changes; never edit an already-applied migration.
- **Dependency/policy:** Reuses authentication, role, ownership, and
  tenant/dealership checks. Do not copy role checks into each route.
- **Adapter:** Isolates external providers behind a small application-owned
  interface when the feature uses email, storage, payments, or another provider.

## 4. Request flow outline

Illustrative outline only. Use existing project imports, response conventions,
shared permission dependencies, and error types; do not copy placeholder names
as if they already exist.

```python
# endpoint: HTTP concerns and delegation only
@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreateRequest,
    current_user: User = Depends(require_roles("authorized_role")),
    db: Session = Depends(get_db),
) -> Item:
    return item_service.create_item(db, current_user, payload)
```

```python
# service: business rules, authorization invariants, and orchestration
def create_item(db: Session, actor: User, payload: ItemCreateRequest) -> Item:
    ensure_actor_can_create_item(actor)
    item = item_repository.create(db, ...)
    return item
```

```python
# repository: persistence only
def get_by_id(db: Session, item_id: int) -> Item | None:
    return db.get(Item, item_id)
```

For sensitive resource operations, check ownership/tenant scope in the operation
as well as enforcing role policy; a role check alone does not establish access to
a particular resource. Use the existing shared error mapping. Do not add
feature-local HTTP error strings or catch broad exceptions.

## 5. Data and transaction rules

- Represent database constraints in the model and migration, and validate user
  input with schemas.
- Keep multi-step state changes in one transaction. Roll back on failure and
  map known integrity conflicts through the established error handling.
- Consider concurrent updates and retries for bookings, counters, invitations,
  and other stateful operations.
- Avoid returning secrets or internal-only model fields from response schemas.
- Use soft deletion only when the domain requires history and follow existing
  lifecycle conventions.

## 6. Test plan

Add focused tests appropriate to the feature:

- **Service/domain:** business invariants, conflicts, not-found cases, and
  rollback/atomicity where applicable.
- **API:** request validation, response shape/status, unauthenticated access,
  insufficient role, cross-tenant/resource access, and normal success.
- **Repository/integration:** persistence constraints and query scoping where
  not adequately exercised through service/API tests.
- **External integrations:** mock the provider boundary and test failures and
  timeouts without making real network calls.

Run the narrow relevant test selection first, then any broader required checks.
Report exactly what ran and any unavailable checks.

## 7. Completion checklist

- [ ] API contract and authorization policy are explicit.
- [ ] Each responsibility is in the correct layer; no duplicated rules.
- [ ] Errors use centralized, established handling.
- [ ] Migrations and configuration changes are safe and documented.
- [ ] Tests cover success, failure, and access-control boundaries.
- [ ] Relevant lint, formatting, type, and test commands pass.
- [ ] API or contributor documentation is updated as needed.
