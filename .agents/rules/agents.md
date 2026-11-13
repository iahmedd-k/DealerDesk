# AGENTS.md

Rules for AI coding assistants. Follow them on every task. If unsure or a rule conflicts with the prompt, ask first.

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

## Architecture (Frontend)
- Typed components (TypeScript, no `any`). Keep components small and reusable.
- Put API calls in a dedicated client/service layer, not inside components.
- Handle loading, empty and error states for every data view.
- Never expose secrets or trust client-side checks for security.
- Keep keyboard accessibility, readable contrast and responsive layout.

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
- Update the README, API docs and `.env.example` when setup, endpoints or config change.

## Reporting
- For big changes, share a short plan and wait for approval.
- When done, summarize: what changed, files touched, what was tested, what to check.
- Flag risks or side effects you notice.