# AGENTS.md - SISEM Frontend Ruleset

## Scope

- Applies only to changes inside `frontend/`.
- If it conflicts with the root `AGENTS.md`, this guide wins.

## Load Narrow Context

- `frontend/src/domains/AGENTS.md` - domain scaffolding and migration flow.
- `frontend/src/infrastructure/api/AGENTS.md` - API client/contracts.
- `frontend/src/components/AGENTS.md` - shared UI/component rules.
- `frontend/src/features/AGENTS.md` - feature-module patterns.
- `frontend/src/features/admin/AGENTS.md` - admin module specifics.
- `frontend/src/app/router/AGENTS.md` - route/guard rules.
- `frontend/src/test/AGENTS.md` - test strategy and execution.

## Skills Reference

- `vercel-react-best-practices` - React performance and refactoring patterns
- `interface-design` - UI layout and visual hierarchy design before implementation
- `web-design-guidelines` - UI/UX and accessibility compliance reviews
- `typescript` - Strict TS types
- `tailwind-4` - Tailwind and `cn()`
- `zod-4` - Zod v4 validation
- `zustand-5` - UI state management
- `error-handling-patterns` - Error contracts and fallback behavior
- `systematic-debugging` - Root-cause-first debugging workflow
- `brainstorming` - Planning and scope definition before implementation
- `playwright` - E2E testing
- `find-skills` - Discover/install skills when requested

## Auto-invoke Skills

| Action | Skill |
| --- | --- |
| Create/modify React components (performance-aware) | `vercel-react-best-practices` |
| Create new UI screens/layout direction before implementation | `interface-design` |
| Review UI/UX/accessibility compliance | `web-design-guidelines` |
| Write TypeScript types | `typescript` |
| Tailwind styling | `tailwind-4` |
| Zod / RHF validation | `zod-4` |
| Create/edit global stores | `zustand-5` |
| Design/review UI and API error states | `error-handling-patterns` |
| Debug bugs, test failures, and regressions | `systematic-debugging` |
| User asks for planning/discovery before coding | `brainstorming` |
| E2E tests | `playwright` |
| User asks to discover/install skills | `find-skills` |

---

## Mandatory Delivery Workflow (Checklist)

- [ ] Scope and acceptance criteria are defined (SDD change or PR description).
- [ ] SDD artifacts are up to date for the current phase.
- [ ] Relevant decisions/discoveries are persisted in Engram (`SISEM_SHARED`).
- [ ] Engram saves use required `topic_key` convention (`feature/{slug}/decision`, `feature/{slug}/progress`, `bug/{id-or-slug}/fix`, `ops/{area}/config`, `docs/{topic}/note`).
- [ ] Required git hooks are active before PR/merge.
- [ ] For NEW features/NEW functionality/LARGE refactors, planning starts with tests-first tasks and execution follows Red -> Green -> Refactor.

---

## Critical Rules - Non-negotiable

### Architecture
- UI never performs HTTP directly; API calls live only in `frontend/src/infrastructure/api/resources/`.
- Server state uses TanStack Query; UI state uses Zustand.
- Prefer Zod-derived types to avoid duplication.
- Keep domain logic outside React components and UI utility helpers.

### Layer Mapping (Frontend)
- `presentation`: React components/pages/routes (rendering, interaction, transport mapping only).
- `application`: hooks/use-cases in domain or feature modules (orchestration and flow decisions).
- `domain`: rules, policies, and domain-specific types.
- `infrastructure`: API clients, adapters, storage/integration utilities.
- Hard ban: critical business rules in `components/`, `routes/`, or `components/ui` helpers.

### React
- Always use named imports from React.
- React Compiler is enabled: avoid `useMemo`/`useCallback` by default; only use manual memoization with measured evidence.

### Styling
- Use semantic tokens from Metro CDMX (no hardcoded colors).
- Never use `var()` inside `className`.

### Security
- JWT must stay in HttpOnly cookies (never localStorage/sessionStorage).
- Mutating requests must include `X-CSRF-TOKEN`.

---

## Domain-First Folder Conventions

- Target domain structure: `frontend/src/domains/<domain>/{components,hooks,pages,state,adapters,types}`.
- Keep shared modules strictly technical (design tokens, primitive UI, API primitives, telemetry).
- Avoid generic shared folders that hold domain decisions (`common`, `misc`, `utils` business logic).
- Cross-domain coordination must happen via API contracts, events, or explicit domain adapters.

## Pattern Guidance (When to Use / Avoid)

- Use hooks/application services for business workflows; keep components as presenters.
- Use repository-like API wrappers when multiple resources/adapters need consistency boundaries.
- Use internal domain events/state signals before introducing external event buses.
- Use policy modules for permission/authorization decisions (not ad-hoc checks in JSX).
- Avoid premature complexity: do not introduce microfrontends, full CQRS, or event sourcing patterns without architecture decision.

## Inter-domain Communication (Mandatory)

- Allowed mechanisms only:
  - API/query contracts through `frontend/src/infrastructure/api/**`.
  - Explicit application orchestration hooks/use-cases for multi-domain UI flows.
  - Event-driven integration only via documented domain events/contracts.
- Hard bans:
  - No direct imports of another domain's internal state/models to bypass contracts.
  - No uncontrolled cross-domain data coupling in components.

## Real-time Communication (Controlled Exception)

- Real-time is not default transport for frontend workflows.
- Recommended use: live notifications, presence, progress updates, operational dashboards.
- Not recommended: security-critical decisions, core CRUD orchestration, or source-of-truth state transitions.
- Keep real-time client logic in dedicated adapters/modules with standardized channel and message contracts.
- WebSocket handlers must delegate business decisions to domain/application hooks.
- Every new real-time flow requires explicit business justification and docs update.

## Audit and Permissions (Frontend Responsibilities)

- Frontend is not the security source of truth; backend authorization prevails.
- Frontend permission checks are UX gating only and must consume centralized permission/policy contracts.
- Do not implement security decisions with ad-hoc role-string checks in JSX/routes.
- When UX exposes sensitive actions, ensure request correlation data (for example `X-Request-ID`) is propagated for backend audit traceability.

## Testing and Evolution Guardrails (Part 3)

- Apply risk-based testing: prioritize unit/integration coverage for feature logic and API contracts; use E2E for critical journeys only.
- Critical frontend flows (authn/authz UX gates, audit traceability metadata propagation, critical clinical transitions, concurrency-prone UI state) require proportional automated coverage before merge.
- Strict TDD-first scope: NEW features, NEW functionality, and LARGE refactors must run Red -> Green -> Refactor.
- Planning/tasking rule: test design and test creation tasks must appear before implementation tasks.
- PR evidence rule: include failing-first proof, implementation progression, and final passing state.
- Exception rule: if TDD cannot be applied, document explicit rationale, compensating controls/tests, and approval in PR review.
- Keep architecture docs as live artifacts: if frontend boundaries or cross-domain flow contracts change, update docs in the same PR.
- Avoid hype-driven architecture shifts (microfrontend/event-bus rewrites) without measurable need and documented decision.
- Preserve canonical blueprint: UI as transport/presentation, behavior in domain/application modules, backend remains security and audit source of truth.

## Frontend PR Checklist

- [ ] Components/routes are presentation-focused, not business-rule containers.
- [ ] Domain/application logic is implemented in hooks/domain modules.
- [ ] Shared modules remain technical and reusable.
- [ ] Permission and contextual rules use policy/dependency modules.
- [ ] Inter-domain communication uses explicit contracts/adapters/events only.
- [ ] Real-time usage (if any) is justified and isolated in dedicated modules.
- [ ] Frontend authz checks are UX-only (no security truth in client role strings).
- [ ] No unnecessary architectural complexity was introduced.
- [ ] Critical user journeys include proportional automated tests by risk.
- [ ] NEW feature/NEW functionality/LARGE refactor includes tests-first tasks and Red/Green/Refactor evidence.
- [ ] Any TDD exception includes explicit rationale, compensating controls/tests, and reviewer approval.
- [ ] Boundary/contract changes update architecture/docs artifacts in the same PR.

---

## Decision Trees

### State Placement
```
Needs server cache/refetch? -> TanStack Query
UI-only state? -> Zustand
Local component state? -> useState
```

### Component Placement
```
Reusable across 2+ features? -> frontend/src/components/
Single feature only? -> frontend/src/features/<feature>/components/
Domain reusable building block? -> frontend/src/domains/<domain>/
Primitive UI? -> frontend/src/components/ui/
```

### API Call Placement
```
HTTP request? -> frontend/src/infrastructure/api/resources/
Transform/adapter? -> frontend/src/infrastructure/api/utils/
Types shared? -> frontend/src/infrastructure/api/types/
```

---

## Commands

```bash
pnpm dev
pnpm lint
pnpm test
```

---

## QA Checklist

- [ ] UI states handled (loading, empty, error)
- [ ] API calls use `frontend/src/infrastructure/api/resources/`
- [ ] No hardcoded colors or `var()` in className
- [ ] Zustand/TanStack Query used appropriately
- [ ] Tests updated when contracts change
- [ ] If domain scaffolding changed, migration notes updated in `docs/guides/incremental-domain-migration.md`
