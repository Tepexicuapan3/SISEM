# AGENTS.md - Backend (Django/DRF) Ruleset

## Scope

- Applies to all files under `backend/`.
- If a deeper `AGENTS.md` exists, that file wins for its subtree.

## Load Narrow Context

- `backend/domains/AGENTS.md` - target domain scaffolding and migration rules.
- `backend/apps/AGENTS.md` - endpoint/use-case/repository implementation details.
- `backend/tests/AGENTS.md` - backend testing workflow.

## Backend Skills

- `django-drf` - DRF implementation patterns.
- `api-design-principles` - API contract and versioning decisions.
- `error-handling-patterns` - error taxonomy, retries, fallback.
- `systematic-debugging` - root-cause-first debugging process.
- `brainstorming` - planning/discovery before implementation.
- `pytest` - backend test patterns.
- `find-skills` - discover/install skills when requested.

## Auto-invoke Skills

| Action | Skill |
| --- | --- |
| Design/review API contracts (resources, status codes, versioning, pagination) | `api-design-principles` |
| Implement Django/DRF endpoints (views, serializers, permissions, filters) | `django-drf` |
| Design/review error contracts and resilience behavior | `error-handling-patterns` |
| Debug backend bugs, test failures, and integration issues | `systematic-debugging` |
| User asks for planning/discovery before coding | `brainstorming` |
| Write backend tests | `pytest` |
| User asks to discover/install skills | `find-skills` |

## Mandatory Delivery Workflow (Checklist)

- [ ] Scope and acceptance criteria are defined (SDD change or PR description).
- [ ] SDD artifacts are up to date for the current phase.
- [ ] Relevant decisions/discoveries are persisted in Engram (`SISEM_SHARED`).
- [ ] Engram saves use required `topic_key` convention (`feature/{slug}/decision`, `feature/{slug}/progress`, `bug/{id-or-slug}/fix`, `ops/{area}/config`, `docs/{topic}/note`).
- [ ] Required git hooks are active before PR/merge.
- [ ] For NEW features/NEW functionality/LARGE refactors, planning starts with tests-first tasks and execution follows Red -> Green -> Refactor.

## Critical Rules

- New backend features must be Django/DRF.
- Keep strict layered boundaries: presentation, application (`use_cases`), domain, infrastructure.
- JWT auth must remain cookie-based (`HttpOnly` cookies).
- Mutating endpoints must enforce CSRF via `X-CSRF-TOKEN`.
- Keep API responses in camelCase when exposed to frontend.
- Keep API routes consistent under `api/v1/` and avoid trailing slash drift.
- DB strategy is domain-first: PostgreSQL is the target engine with `DB per domain` ownership.
- Every table/schema/migration must have a single domain owner; avoid shared tables without explicit owner.
- No direct cross-domain SQL access from backend code (reads/writes); use API contracts, events, or read-models.

## Database Integrity and Concurrency (Part 3)

- Stage policy alignment: in early stages, backend runs on shared PostgreSQL engine/instance with strict domain ownership and logical boundaries; physical DB split is evaluated later by documented criteria.
- Enforce integrity by design: explicit PK/FK, uniqueness, nullability, and indexes based on actual query patterns.
- Define transaction boundaries in use cases/application services for critical operations.
- For concurrency-sensitive workflows, document and choose safe write strategy (`SELECT ... FOR UPDATE`, optimistic locking/version checks, idempotency keys, or queue serialization).
- Keep operational transactional state separate from append-only audit/history storage.

## Inter-domain Communication (Mandatory)

- Allowed mechanisms only:
  - Formal query/service contract for deterministic sync calls.
  - Orchestrator use case in application layer for ordered multi-domain workflows.
  - Domain events (internal first) for decoupled side effects.
- Hard bans:
  - No imports/dependencies on another domain's internal models/repositories/business rules.
  - No uncontrolled cross-domain data access.

## Real-time Communication (Controlled Exception)

- Default transport remains request/response APIs.
- Use real-time only when justified (notifications, presence, progress streams, low-latency dashboards).
- Do not use real-time handlers for security-critical decisions, core CRUD orchestration, or primary audit persistence.
- Keep real-time handlers thin; delegate critical behavior to application use cases.
- Enforce standardized channel naming, auth checks, and message contracts in dedicated modules.

## Audit and Authorization Baseline (Mandatory)

- Audit coverage is required for auth events, sensitive reads/writes, and critical operations.
- Minimum audit event fields: `actor`, `timestamp`, `action`, `domain`, `resource`, `result`, `contextId/requestId`; plus `ip`/`userAgent` when available; plus `beforeState`/`afterState` on mutations.
- Audit implementation must combine explicit use-case logging and automated hooks for sensitive pathways.
- Audit storage must be append-only, access-restricted, and sensitive fields must be masked/redacted.
- Authorization base is atomic permissions; roles are bundles only.
- Use centralized policy/authorization services; do not rely on ad-hoc role-string checks.
- Backend remains the security source of truth.

## Architecture Responsibilities (Backend)

- `presentation`: DRF views/serializers/permissions; transport mapping only.
- `application`: use cases orchestration, transaction boundaries, workflow coordination.
- `domain`: entities/value objects/invariants/policies.
- `infrastructure`: ORM repositories, external gateways, technical adapters.
- Hard ban: critical business logic in `views.py`, `serializers.py`, `forms.py`, middleware, or helper utils.

## Pattern Guidance (When to Use / Avoid)

- Use Cases: default entrypoint for business operations.
- Repository pattern: use only when persistence complexity, consistency, or multi-source orchestration needs an abstraction; avoid thin pass-through wrappers over ORM.
- Domain events: emit internal events first; add external events only with explicit integration needs.
- Policies: isolate authorization/contextual rules in policy modules, not in views.
- Transactions: define boundaries in application/use-case layer; avoid nested transaction handling in presentation.
- Avoid premature complexity: no microservices split, no full CQRS, no full event sourcing without documented architecture decision.

## Strict TDD-First Governance (Mandatory)

- Scope: NEW features, NEW functionality, and LARGE refactors.
- Planning must place testing design/creation tasks before implementation tasks.
- Execution must follow Red -> Green -> Refactor (fail first, minimal passing implementation, behavior-preserving refactor).
- PRs must include test-first evidence (initial failing tests, implementation progression, final passing state).
- If TDD cannot be applied, document explicit rationale, define compensating controls/tests, and require approval in PR review.

## Backend PR Checklist

- [ ] Presentation layer only maps transport and delegates to use cases.
- [ ] Use cases contain business orchestration and transaction boundaries.
- [ ] Domain rules/invariants are not implemented in serializers or views.
- [ ] Repository abstraction is justified by complexity/consistency needs.
- [ ] No direct cross-domain DB/table/schema access.
- [ ] Inter-domain communication uses only contract/orchestrator/event mechanisms.
- [ ] Real-time usage (if any) is justified and delegates critical logic to use cases.
- [ ] Critical operations include audit coverage with required fields.
- [ ] Authorization uses atomic permissions and centralized policies.
- [ ] DB changes document integrity constraints, transaction boundaries, and concurrency strategy.
- [ ] Critical backend features include proportional automated tests based on risk.
- [ ] NEW feature/NEW functionality/LARGE refactor includes TDD-first evidence (tests-first tasks + Red/Green/Refactor trace).
- [ ] Any TDD exception is explicitly justified with compensating controls/tests and reviewer approval.
- [ ] Any architecture boundary/flow change updates the related docs in the same PR.

## Backend Structure

- `backend/config/` - settings and root URLs.
- `backend/apps/` - domain apps.
- `backend/domains/` - domain-first target structure (incremental scaffolding, no runtime cutover yet).
- `backend/infrastructure/` - cross-cutting integrations.
- `backend/tests/` - backend tests and fixtures.

## Incremental Migration Guardrails (`apps` -> `domains`)

- Do not move legacy modules in one shot; migrate per completed pilot domain.
- Keep active runtime routes in `backend/apps/` until domain DoD is complete.
- Allow temporary wrappers/adapters (documented) between `apps` and `domains`.
- Every PR must state domain status: `legacy`, `hybrid`, or `domain-first`.
- PostgreSQL migration must follow `expand -> migrate -> contract` per domain; no big-bang cutover.

## Commands

```bash
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test
```
