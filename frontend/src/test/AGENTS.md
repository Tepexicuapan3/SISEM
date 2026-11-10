# AGENTS.md - Frontend Testing Guide

## Scope

- Applies to `frontend/src/test/**`.
- If it conflicts with `frontend/AGENTS.md`, this file wins.

## Skills Reference

- `playwright` - E2E strategy and browser workflows.
- `systematic-debugging` - root-cause-first debugging for flaky/failing tests.
- `typescript` - typed test utilities and fixtures.
- `error-handling-patterns` - assert error and fallback behavior.
- `brainstorming` - plan broader testing strategy before coding.
- `find-skills` - discover/install skills when requested.

## Auto-invoke Skills

| Action | Skill |
| --- | --- |
| Create/maintain E2E tests | `playwright` |
| Debug failing or flaky tests | `systematic-debugging` |
| Write typed fixtures/utilities | `typescript` |
| Validate UI/API error behavior in tests | `error-handling-patterns` |
| User asks for planning/discovery before coding | `brainstorming` |
| User asks to discover/install skills | `find-skills` |

## Testing Rules

- Keep tests deterministic and isolated.
- Prefer condition-based waiting over fixed sleeps/timeouts.
- Cover loading, empty, success, and error states.
- Reuse factories/mocks from `frontend/src/test/factories` and `frontend/src/test/mocks`.
- Keep MSW handlers aligned with current API contracts.

## Risk-Based Test Strategy (Part 3)

- Testing pyramid baseline:
  - unit/integration for component behavior, hooks, adapters, and API contracts,
  - E2E for critical user journeys only.
- Priority coverage areas:
  - auth/authz UX gates and policy-dependent visibility,
  - backend audit traceability signals (for example request correlation propagation),
  - critical clinical flows and state transitions,
  - concurrency-prone UI behavior (race-prone async transitions and optimistic updates).
- Merge rule: critical frontend flows need proportional automated coverage based on risk and user impact.

## Strict TDD-First Governance (Mandatory)

- Scope: NEW features, NEW functionality, and LARGE refactors.
- Test design/creation tasks must be first in planning before implementation tasks.
- Execution cycle is mandatory: Red -> Green -> Refactor.
- PR evidence must show failing-first tests, implementation progression, and final passing state.
- If TDD cannot be applied, document explicit rationale and compensating controls/tests with PR approval.

## Part 2 Verification Hooks

- Add coverage for cross-domain UI flows using explicit contracts/adapters/events, not direct internal coupling.
- If real-time UI behavior is present, verify handlers delegate business/security decisions to domain/application logic.
- For sensitive actions, assert request correlation metadata is sent when required for backend audit traceability.
- Verify permission UX gates map to atomic permissions/policy dependencies and avoid ad-hoc role-string checks.

## Commands

```bash
bun test
```
