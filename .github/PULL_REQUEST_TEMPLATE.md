## Summary

<!-- Describe the user-visible or operational change and why it is needed. -->

## Change type

- [ ] Feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Documentation
- [ ] Security
- [ ] Other:

## Implementation

- [ ] The change follows the established project architecture and naming conventions.
- [ ] Business rules are implemented once and shared; no unnecessary duplication was added.
- [ ] API routes delegate business logic to services.
- [ ] Database access is isolated in repositories.
- [ ] Request and response schemas are explicit; updates whitelist allowed fields.
- [ ] Authorization and resource ownership are checked server-side.
- [ ] Errors use the established error contract and do not expose internal details.
- [ ] Configuration and secrets use the project's configuration mechanisms.
- [ ] Database changes use a new migration; existing migrations were not rewritten.
- [ ] Documentation and examples were updated where behavior or setup changed.

## Security and data

- [ ] Inputs, permissions, ownership, and tenant/dealership scope were reviewed.
- [ ] No secrets, tokens, credentials, or personal data were added to source or logs.
- [ ] Multi-step writes are atomic, and retry-sensitive operations are safe.
- [ ] External services are accessed through the existing adapter/integration boundary.
- [ ] Any security-relevant behavior and failure cases are covered.

## Tests and verification

- [ ] Tests cover the happy path, relevant edge cases, and failure behavior.
- [ ] Relevant tests pass (command/output):
- [ ] Lint/format/type checks pass, where configured (command/output):
- [ ] Any skipped or unavailable checks are explained:

## Risks and rollout

- **Risk / compatibility impact:** None / describe
- **Migration or configuration required:** None / describe
- **Rollback considerations:** None / describe

## Reviewer notes

<!-- Include API examples, screenshots, test data, or decisions reviewers should know. -->
