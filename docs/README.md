# DealerDesk Documentation

Welcome to the DealerDesk documentation. This directory describes the system **as it is currently implemented** in the repository. It is written for developers, reviewers, and operators who need to understand, run, extend, or deploy the service.

> **Snapshot:** API version `0.1.0`, generated from the current working tree (November 2026).
> Update these documents whenever behaviour, endpoints, configuration, or data models change.

## Documentation map

| Document | Audience | Purpose |
| --- | --- | --- |
| [Overview](overview.md) | Everyone | Product scope, implemented capabilities, current status |
| [Architecture](architecture.md) | Engineers | System design, layers, components, request lifecycle |
| [Data Model](data-model.md) | Engineers, DBAs | Tables, relationships, constraints, lifecycle rules |
| [Authentication](authentication.md) | Engineers, Security | Identity, tokens, roles, authorization, reset flows |
| [API Reference](api-reference.md) | API consumers, Frontend | Every implemented endpoint and its contract |
| [Configuration](configuration.md) | Operators, Engineers | Environment variables and external services |
| [Getting Started](getting-started.md) | New contributors | Local setup, database, run, seed, verify |
| [Testing](testing.md) | Contributors | Test strategy, fixtures, and how to run suites |
| [Deployment](deployment.md) | Operators | Runtime behaviour, startup, production checklist |
| [Development Guide](development.md) | Contributors | Layout, conventions, and how to add features |
| [Backend Feature Template](backend-feature-template.md) | Contributors | Layered implementation outline and completion checklist for backend features |
| [Roadmap & Limitations](roadmap.md) | Everyone | Implemented vs. not implemented, known risks |

## System at a glance

DealerDesk is a multi-dealership vehicle dealership management backend. It provides:

- Customer and dealership account management with JWT authentication.
- Dealership workspaces with timezone-aware configuration.
- Brand and vehicle inventory management with soft-delete history.
- Staff invitations, roles, and lifecycle management.
- Test-drive scheduling with capacity, timezone, and DST handling.
- Optional transactional email (Resend) and Supabase Storage for brand logos.

**Stack:** FastAPI · SQLAlchemy 2.0 · PostgreSQL · Pydantic v2 · PyJWT · Argon2 · pytest · Ruff.

**Status:** Backend implemented. The `frontend/` directory currently contains dependencies only; no frontend source is implemented. See [Roadmap & Limitations](roadmap.md).

## Quick links

- Interactive API docs (when running): `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`
- Backend developer notes: [`backend/Readme.md`](../backend/Readme.md)
