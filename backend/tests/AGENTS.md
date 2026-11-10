# AGENTS.md - Backend Testing Guide

## Scope

- Applies to `backend/tests/**`.
- If it conflicts with `backend/AGENTS.md`, this file wins.

## Skills Reference

- `pytest` - backend testing patterns and structure.
- `systematic-debugging` - failing test investigation by root cause.
- `error-handling-patterns` - validating API/domain error behavior.
- `brainstorming` - planning test strategy before broad changes.
- `find-skills` - discover/install skills when requested.

## Auto-invoke Skills

| Action | Skill |
| --- | --- |
| Write/refactor backend tests | `pytest` |
| Diagnose flaky/failing tests | `systematic-debugging` |
| Validate error contracts in tests | `error-handling-patterns` |
| Plan test strategy before large refactors | `brainstorming` |
| User asks to discover/install skills | `find-skills` |

## Test Rules

- Prefer deterministic tests: no arbitrary sleeps, no hidden ordering assumptions.
- Backend tests may run with in-memory SQLite as a test-only exception (`python manage.py test`).
- Test SQLite does not redefine SISEM data policy: PostgreSQL remains the domain ownership target for runtime/production.
- Cover both happy path and failure path for each endpoint/use case touched.
- Assert standard error payload shape (`code`, `message`, `status`, optional `details`, optional `requestId`).
- Keep fixtures/data builders explicit and local to the suite when possible.
- Avoid coupling tests to implementation details that can change without contract impact.

## Risk-Based Test Strategy (Part 3)

- Testing pyramid baseline:
  - Unit/service tests as default for business rules and policy logic.
  - Integration/API tests for contract boundaries and cross-layer behavior.
  - E2E only for critical end-to-end clinical journeys.
- Priority coverage areas:
  - authentication/authorization/security controls,
  - audit traceability and correlation IDs,
  - critical clinical workflows and state transitions,
  - concurrency-sensitive operations (locking/idempotency/versioning behavior).
- Merge rule: critical backend features require proportional automated coverage based on risk and blast radius.

## Strict TDD-First Governance (Mandatory)

- Scope: NEW features, NEW functionality, and LARGE refactors.
- Test planning and creation tasks must appear before implementation tasks.
- Enforce Red -> Green -> Refactor: tests fail first, pass with minimal implementation, then refactor while preserving behavior.
- PR evidence must include failing-first proof, implementation progression, and final passing state.
- If TDD is not applicable, require explicit rationale plus compensating controls/tests approved in PR review.

## Part 2 Verification Hooks

- For cross-domain flows, assert usage through approved contracts/orchestrators/events (not direct table ownership violations).
- If real-time behavior exists, assert business-critical decisions are enforced in use cases, not transport handlers.
- For critical operations, validate audit contract coverage (including correlation IDs and mutation snapshots when applicable).
- Validate authorization on atomic permissions/policies; do not treat role-string checks as sufficient backend security.

## Execution

```bash
python manage.py test
```
