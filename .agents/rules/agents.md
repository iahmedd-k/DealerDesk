# AGENTS.md

Rules for AI coding assistants. Follow them on every task. If unsure or a rule conflicts with the prompt, ask first.

These standards apply equally to code written, generated, edited, or proposed
with AI assistance; AI-generated code is not exempt from review, testing, or
project conventions.

## Git
- Never `git push`, force push, or open a PR unless I explicitly ask.
- Commit only when asked. Use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- Never mention Copilot or add Copilot attribution, trailers, or co-authorship in commit messages.
- Never rewrite history or switch/delete branches without asking.
- Work on a feature branch, not `main`.

## Safety
- Never delete or replace an existing feature, endpoint or file without my approval. Explain what and why first.
- Ask a clarifying question when a request is ambiguous or could break existing behavior.
- No destructive commands (`rm -rf`, dropping DBs, wiping volumes, resetting migrations) without asking.
- Never commit secrets or `.env`. Use env vars and keep `.env.example` updated.
- No new dependencies without asking.

## Scope
- Make the smallest change that solves the task. No unrelated refactors or reformatting.
- Follow existing patterns, naming and folder structure.
- Do not guess APIs, libraries or file paths. Check the code or docs.

## Architecture (Backend)
- Layers: **routes** (thin) → **services** (business logic) → **repositories** (all DB access).
- No SQL/ORM queries outside repositories.
- External providers (LLM, email, messaging, payments) go behind an interface/adapter.
- Validate all input at the boundary with typed schemas (e.g. Pydantic). Keep DB models and API schemas separate.
- Schema changes via migrations only. Never edit old migrations or the DB by hand.
- Use consistent API responses, error format, pagination and versioned routes (`/api/v1`).
- Check authentication and authorization server-side on every protected route.
- Wrap multi-step writes in transactions. Make retried operations idempotent.
- Centralize cross-cutting logic: authentication, authorization, validation, error mapping, logging, pagination, and response formatting. Do not re-implement the same checks/messages in every endpoint.
- Use a single source of truth for business rules and role checks. Prefer reusable permission helpers, policy functions, or service methods over repeating `if current_user.role ...` blocks in every function.
- Define domain exceptions or a centralized API error handler and map them consistently to HTTP statuses. Endpoints should not duplicate repeated error strings, status codes, and response shapes.
- Prefer composition and shared helpers over copy-paste logic. If two or more endpoints need the same validation, permission check, or error mapping, extract it once and reuse it.
- Keep route handlers free of business logic, data mutation details, and duplicated authorization logic.
- Use role and permission constants or enums instead of raw magic strings repeated throughout the codebase.

## Professional Architecture Rules
- One business rule = one place. Do not duplicate logic across routes, services, or scripts.
- Domain boundaries are explicit: route layer handles HTTP concerns, service layer handles business logic, repository layer handles persistence, and adapters isolate external systems.
- Authorization must be policy-based, not ad hoc. Centralize “who can do what” in permission helpers, role checks, or access-control services.
- Validation must happen at the boundary and again where business rules require it; validate user input, entity state, and permission state before writing.
- Maintain consistent error contracts and logging across the entire app so clients and operators get the same behavior everywhere.
- Keep modules focused, reusable and testable; no giant endpoint files that mix validation, authorization, database access, and domain logic.
- Prefer small, named services per domain (`dealership_service`, `vehicle_service`, etc.) instead of route-local functions with large if-blocks.

## Backend Code Review Checklist
- Use the repository checklist in `.github/PULL_REQUEST_TEMPLATE.md` for every
  pull request and review, including review of changes before a PR is opened.
- Route files must only parse HTTP inputs and delegate to services.
- Services must not contain raw SQL/ORM queries directly; repositories own persistence.
- Repeated validation, permission logic, and error strings must be centralized and reused.
- Data models must not leak directly into responses without explicit schemas.
- Every public endpoint must enforce auth/authorization server-side.
- Business rules must be tested at the service layer and API boundary.
- New code must not duplicate existing helpers, patterns, or constants.
- Any new dependency, migration, or external API integration must be justified and documented.
- No dead code, commented-out logic, or unused branches.
- Every change must preserve the existing error contract and response structure.

## API Security Baseline
- Require authentication on all protected endpoints and validate user identity every time.
- Enforce authorization based on role, ownership, or policy for every resource access.
- Do not trust client-provided IDs, role flags, or permission claims.
- Validate all incoming payloads with schemas and reject malformed or unexpected data.
- Prevent mass assignment and unsafe updates by whitelisting allowed fields.
- Use explicit checks for ownership and dealership scoping before mutate/delete actions.
- Normalize and validate email, timezone, URLs, and IDs before persisting or exposing them.
- Use transactional writes for multi-step state changes and avoid partial updates.
- Return structured, consistent 4xx/5xx errors without leaking internal system details.
- Log security-relevant events without exposing secrets or personal data.

## Project Folder Conventions
- Keep code organized by responsibility: `api/`, `core/`, `db/`, `dependencies/`, `models/`, `repositories/`, `schemas/`, `services/`, `utils/`, `tests/`.
- Do not mix route logic, business logic, persistence logic, and schemas in the same file.
- One domain = one service and preferably one repository when persistence is needed.
- Shared helpers belong in `core/` or `utils/` only when they are truly reusable and not domain-specific.
- Tests live with the relevant feature or domain and follow the existing project structure.
- Files must use clear domain names (`dealership_service.py`, `user_repository.py`) instead of generic or ambiguous names.
- Keep feature-related files close to the domain they serve; avoid cross-cutting logic spread across unrelated folders.
- Use `docs/backend-feature-template.md` as the starting checklist when creating
  a backend feature or domain. Treat it as guidance, not a requirement to add
  unnecessary layers or files.

## Frontend Architecture Standards
- Typed components (TypeScript, no `any`). Keep components small and reusable.
- Put API calls in a dedicated client/service layer, not inside components.
- Handle loading, empty and error states for every data view.
- Never expose secrets or trust client-side checks for security.
- Keep keyboard accessibility, readable contrast and responsive layout.
- Centralize API error handling and user-facing error mapping in one frontend layer.
- Separate UI state from business state; keep components presentational when possible.
- Use shared hooks and utilities for repeated behaviors instead of duplicated component logic.
- The frontend is not implemented yet; when it is introduced, confirm the
  framework and existing conventions first, then apply these standards without
  assuming a specific frontend stack.

## AI-Assisted Change Standard
- Read and follow this file before exploring or changing project code. Inspect
  the target code and existing patterns before choosing an implementation.
- Apply the same architecture, security, testing, documentation, and review
  requirements to AI-generated code as to human-written code.
- Do not generate speculative APIs, layers, dependencies, or boilerplate.
  Reuse verified project helpers and add only what the requested behavior needs.
- Verify generated changes with the narrowest relevant tests and checks; never
  claim a check passed unless it was run successfully.
- Explain any necessary deviation from these standards and surface unresolved
  risks or unavailable verification in the final report.

## Naming and Dependency Rules
- Use domain-first names: `dealership_service`, `user_repository`, `auth_service`, `DealershipRegistrationRequest`.
- Use noun-based models and verb-based services; repositories should read/write domain entities, not coordinate workflows.
- Prefer dependency direction: routes → services → repositories → models. Never invert this.
- Services depend on repositories and shared utilities; they should not depend on route code or HTTP-specific objects.
- Repositories should not depend on services or API schemas.
- Avoid circular dependencies between modules and services.
- Use consistent naming across layers: singular domain nouns, lowercase file names, and predictable function names.
- Prefer explicit, descriptive names over abbreviations unless already established in the project.

## Code Quality
- Type hints everywhere. Run the linter and formatter before finishing.
- Handle errors explicitly. Never swallow exceptions.
- No hardcoded URLs, keys, IDs or magic numbers. Use config.
- Use structured logging, not `print`/`console.log`. Never log secrets or personal data.
- Comments explain *why*, not *what*.

## Testing
- Add proper tests for every feature and bug fix, in the existing test folders and framework.
- Cover happy path, edge cases and failures. Mock external services.
- Run relevant tests before saying done. Report results honestly.
- Never delete, skip or weaken a test to make it pass. Explain and ask instead.

## Cleanup
- Delete temp, scratch, debug and backup files you created before finishing.
- Leave no dead code, unused imports or commented-out code.
- Only delete files you created this task.

## Docs
- For every code, design, feature, bug-fix, or behavior change, update the
  relevant documentation under `docs/` in the same change. This is mandatory
  regardless of change size.
- Keep architecture, API, setup, configuration, and user-facing docs aligned
  with the implemented behavior; do not document planned behavior as if it were
  implemented.
- When adding or renaming a documentation file, update the relevant docs index
  or links. Update the README, API docs, and `.env.example` when the change
  affects their subject matter.
- Do not mark a change complete until its relevant documentation is updated.

## Reporting
- For big changes, share a short plan and wait for approval.
- When done, summarize: what changed, files touched, what was tested, what to check.
- Flag risks or side effects you notice.