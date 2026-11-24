# Development Guide

This guide describes the repository conventions and how to add features without breaking existing behaviour.

## Repository layout

```text
DealerDesk/
├── backend/        # FastAPI service (implemented)
├── frontend/       # Not implemented; currently contains node_modules only
├── docs/           # This documentation
└── .agents/        # AI assistant rules for this repository
```

## Backend conventions

The repository rule file `.agents/rules/agents.md` defines the standards. Key points:

### Layering

- Routes are thin: parse/validate, authorize, delegate, shape the response.
- Business logic belongs in `app/services/`.
- Database access should go through `app/repositories/`.
- Keep SQLAlchemy models and Pydantic schemas separate.

> Current reality: auth and dealership flows follow this layering; brands, vehicles, staff, and test-drive endpoints currently query the database directly. New work should prefer repositories and, when touching those modules, consider extracting queries rather than adding more inline ones.

### Validation

- Define request/response models in `app/schemas/`.
- Enforce ranges, patterns, and enums in Pydantic where possible.
- Never trust client-side checks for security.

### Database changes

- Schema is created/altered at startup by `create_all` plus `app/db/migrations.py`.
- Add a new idempotent migration function for non-trivial changes and call it from the lifespan in `app/main.py`.
- Wrap multi-step writes in a single transaction and roll back on `IntegrityError`.
- Use `SELECT ... FOR UPDATE` for concurrency-sensitive reads.
- Do not edit production data by hand.

### Errors

- Raise `HTTPException` with a clear `detail` and the correct status code.
- Treat cross-dealership access as `404` to avoid disclosure.
- Use `409` for conflicts, `422` for semantic validation, `503` for missing configuration.

### Security and secrets

- Never commit `.env`; update `.env.example` when configuration changes.
- Keep secrets in environment variables and access them through `get_settings()`.
- Do not log tokens, passwords, or personal data.

### Logging

- Use module-level `logging.getLogger(__name__)` rather than `print`.
- The application startup message is emitted through the module logger.

## Common tasks

### Add a new endpoint

1. Create or extend a schema in `app/schemas/`.
2. Implement business logic in a service, and data access in a repository when practical.
3. Add a router in `app/api/v1/endpoints/` and register it in `app/api/v1/router.py`.
4. Protect it with `get_current_user` and/or `require_roles(...)`.
5. Apply dealership scoping checks.
6. Add tests under `backend/tests/`.
7. Update the [API Reference](api-reference.md) and `.env.example` if needed.

### Add a table or column

1. Add or update the SQLAlchemy model in `app/models/`.
2. Export new models from `app/models/__init__.py`.
3. Add an idempotent migration in `app/db/migrations.py` if `create_all` is insufficient.
4. Call it from the lifespan.
5. Add integration tests that exercise constraints.
6. Update the [Data Model](data-model.md).

### Add a background/external integration

- Put the provider behind a small module in `app/services/` with a clear function signature.
- Read credentials from settings.
- Return a status instead of raising for optional delivery failures, following `email_service`.
- Mock the provider in tests.

## Code style

- Python with full type hints.
- Avoid comments unless they explain *why*.
- Keep functions focused; prefer small helpers.
- Follow the existing import and formatting style.
- Run ruff before finishing:

```powershell
ruff check .
ruff format --check .
```

## Testing workflow

```powershell
cd backend
$env:TEST_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/dealerdesk_test"
pytest
```

See [Testing](testing.md) for fixtures and coverage.

## Git and review

- Work on a feature branch, not `main`.
- Do not push or open pull requests unless explicitly asked.
- Commit only when asked, using Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Summarize changes, files touched, tests run, and any risks.

## Documentation expectations

Update these documents when you change:

- Endpoints or payloads → [API Reference](api-reference.md)
- Configuration → [Configuration](configuration.md) and `.env.example`
- Tables/constraints → [Data Model](data-model.md)
- Auth/roles → [Authentication](authentication.md)
- Operational behaviour → [Deployment](deployment.md)
- Scope or limitations → [Roadmap & Limitations](roadmap.md)

## Related documents

- [Architecture](architecture.md)
- [Getting Started](getting-started.md)
- [Testing](testing.md)
