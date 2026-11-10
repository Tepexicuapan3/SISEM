# AGENTS.md - Frontend Source Onboarding Guide

## Scope

- Applies to `frontend/src/**`.
- If a deeper `AGENTS.md` exists, that file wins for its subtree.

## Purpose

- Provide quick onboarding for contributors touching React runtime code.
- Document the canonical ownership after the Phase 1-4 source-root reorganization.

## Mandatory Delivery Workflow (Checklist)

- [ ] Scope and clear acceptance criteria are defined (SDD change or PR description).
- [ ] SDD artifacts are current for the change phase (proposal/spec/design/tasks/apply/verify).
- [ ] Relevant decisions/discoveries are persisted in Engram (`SISEM_SHARED`).
- [ ] Engram saves use required `topic_key` convention (`feature/{slug}/decision`, `feature/{slug}/progress`, `bug/{id-or-slug}/fix`, `ops/{area}/config`, `docs/{topic}/note`).
- [ ] Required git hooks are active before PR/merge.
- [ ] NEW feature/NEW functionality/LARGE refactor uses tests-first planning and Red -> Green -> Refactor execution evidence.

## Architecture Guardrails (Part 1-3 baseline)

- Keep modular-monolith + pragmatic DDD boundaries even in frontend modules.
- Respect layered responsibilities:
  - `presentation`: components, pages, routes.
  - `application`: hooks/use-cases and orchestration.
  - `domain`: business rules/policies/types.
  - `infrastructure`: API clients/adapters/integration utilities.
- Critical business rules must not live in JSX, route guards, or shared UI helpers.

## Source-Root Canonical Structure

```text
frontend/src/
  app/
    bootstrap/
    config/
    providers/
    router/
      guards/
      modules/
    navigation/
    state/ui/
  infrastructure/
    api/
    realtime/
      core/
      adapters/
      streams/visits/
  shared/
    ui/
    components/
    layouts/
    hooks/
    utils/
      styling/
      web/
      identity/
    styles/
  test/
```

## Canonical Aliases (Phase 4)

- Core:
  - `@app/*` -> `src/app/*`
  - `@infra/*` -> `src/infrastructure/*`
  - `@shared/*` -> `src/shared/*`
- Optional shortcuts:
  - `@api/*` -> `src/infrastructure/api/*`
  - `@routes/*` -> `src/app/router/*`
  - `@realtime/*` -> `src/infrastructure/realtime/*`
- Legacy transition aliases with `@/...` for api/routes/realtime/components/config/providers/store/styles/hooks are closed in this phase and must not be reintroduced.

## Folder Ownership (What goes / What does NOT go)

### `app/`
- ✅ App composition and runtime shell: bootstrap, top-level providers wiring, router composition, navigation shells, global UI state wiring.
- ❌ Domain business rules, endpoint logic, or reusable visual primitives.

### `infrastructure/`
- ✅ Transport and integration adapters: HTTP client layer, realtime connection primitives, stream adapters.
- ❌ JSX page composition, domain decision rules, or feature-specific presentation logic.

### `shared/`
- ✅ Cross-cutting technical assets reusable across contexts: UI primitives, generic components/layouts, utility helpers, shared styles.
- ❌ Business policies/invariants, domain permission logic, or flow orchestration tied to one bounded context.

### `test/`
- ✅ Frontend test setup, factories, mocks, and test-only helpers.
- ❌ Runtime production code.

## Migration Scope Notes

- `features/` and `domains/` remain in coexistence mode for gradual domain-first migration.
- Structural/root-level migrations must preserve runtime behavior (no functional logic changes).
- When touching imports, prefer canonical aliases above and avoid creating new `@/...` transition paths.

## Layer/Import Boundary Rules (Anti-coupling)

- UI/presentation modules consume contracts/hook APIs; they must not open transport connections directly.
- `app/**` can depend on `infrastructure/**` and `shared/**`, but not the reverse.
- `shared/**` must stay dependency-light and must not import app runtime orchestration.
- `infrastructure/**` must expose integration contracts/adapters and remain free of domain business rules.
- Keep cross-context integration through explicit contracts (API/events/adapters), not internal module reach-through.

## Inter-domain, Real-time, and Authorization Guardrails (Part 2)

- Inter-domain communication in frontend must use explicit contracts/adapters/events only.
- Do not bypass boundaries through direct imports of another module's internals.
- Real-time is a controlled exception: use dedicated modules/contracts and keep handlers thin.
- WebSocket/event handlers must delegate business decisions to application/domain hooks.
- Frontend permission checks are UX gating only; backend authorization remains source of truth.
- Do not use ad-hoc role-string checks in components/routes as security enforcement.

## Audit Awareness (Frontend)

- For sensitive UX flows, propagate correlation metadata required by backend audit (`X-Request-ID` when applicable).
- Never treat client-side logs/events as canonical audit persistence.

## Start Here

- `frontend/AGENTS.md`
- `frontend/src/README.md`
- `frontend/src/test/AGENTS.md`
- `frontend/src/app/router/AGENTS.md`
