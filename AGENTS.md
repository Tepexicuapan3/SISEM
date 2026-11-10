# AGENTS.md - SISEM Operating Guide

## Scope

- Base guide for the whole repository.
- More specific `AGENTS.md` files override this guide for their subtree.

## Project Snapshot

SISEM is a clinical system with React 19 + Vite on frontend and Django 5 + DRF on backend.
All new backend functionality must be built for Django/DRF.

## Operating Baseline (Phase 1)

- Official strategy: evolutionary modular monolith + `DB per domain` with PostgreSQL as target engine.
- Mandatory delivery flow: SDD phases + TDD-first planning/execution + Engram persistence + PR review. Jira is no longer used (`docs/governance/decision-sin-jira.md`).
- Runtime remains on current routes/modules until each domain reaches DoD (no big-bang cutover).
- Auth functional refactor starts only after planning artifacts and acceptance criteria (SDD/PR) are ready.

## Scoped Guides (Load Narrow Context First)

- `backend/AGENTS.md` - backend-wide rules
- `backend/domains/AGENTS.md` - domain scaffolding backend (target structure)
- `backend/apps/AGENTS.md` - endpoint/use-case/repository implementation
- `backend/tests/AGENTS.md` - backend testing workflow
- `frontend/AGENTS.md` - frontend-wide rules
- `frontend/src/domains/AGENTS.md` - domain scaffolding frontend (target structure)
- `frontend/src/api/AGENTS.md` - API client/contracts in frontend
- `frontend/src/components/AGENTS.md` - shared UI/component rules
- `frontend/src/features/AGENTS.md` - feature-module rules
- `frontend/src/features/admin/AGENTS.md` - admin feature specifics
- `frontend/src/routes/AGENTS.md` - routing/guards
- `frontend/src/test/AGENTS.md` - frontend testing workflow
- `docs/AGENTS.md` - docs-wide rules
- `docs/api/AGENTS.md` - API documentation contracts

## Domain-First Operating Model (Phase 1 + base Phase 2)

- Delivery is organized by domains with explicit ownership (backend + frontend + DB + docs per domain).
- No big-bang moves: `old` and `new` coexist until pilot domains are completed.
- Current routes/runtime remain the source of operation; new structures are introduced as gradual scaffolding.
- Mandatory data strategy: `DB per domain` with PostgreSQL as target technology for scalability.
- Domain data isolation: first logical (schema/namespace ownership), then physical (dedicated DB) based on documented criteria.
- Direct cross-domain access to tables/schemas is prohibited; use contracts (API/events/read-models).
- Cross-domain changes require a short RFC and PR impact checklist.

## Architecture and Organization Standards (Operationalized)

These rules convert team standards into mandatory repository behavior for AI agents.

### 1) Recommended Architecture (mandatory)

- Keep SISEM as an evolutionary modular monolith with pragmatic, lightweight DDD.
- Apply layered architecture in every domain/module:
  - `presentation` (API/UI transport, validation, mapping)
  - `application` (use cases, orchestration, transaction boundaries)
  - `domain` (business invariants, entities/value objects, domain policies)
  - `infrastructure` (ORM, external services, adapters)
- Critical business rules MUST live in `application` and `domain`, never in transport layers.
- Hard ban: do not put critical business logic in views, serializers, forms, route handlers, React components, or UI utility helpers.

### 2) Folder Organization by Business Domain (mandatory)

- Organize by business domain first, then by layer inside each domain.
- Backend target: `backend/domains/<domain>/{presentation,use_cases,infrastructure,domain,tests}`.
- Frontend target: `frontend/src/domains/<domain>/{components,hooks,pages,state,adapters,types}`.
- Shared modules are controlled and limited to technical cross-cutting concerns (design tokens, API client primitives, logging, telemetry, shared test tools).
- Hard ban: generic "misc/common/utils" modules containing domain business decisions.
- Hard ban: direct cross-domain DB access from application code; use contracts (API/events/read-models).

### 3) Recommended Design Patterns (use intentionally)

- Use Cases / Application Services: default for business operations.
- Repository Pattern: use when persistence complexity, transactional consistency, or multi-source orchestration justifies abstraction.
- Domain Events (internal first): publish internal domain events before introducing external integration events.
- Policies: centralize authorization and contextual business permission rules in dedicated policy objects/functions.
- Transactions: open and close transactional boundaries at the application layer.
- Avoid premature complexity:
  - Do not split to microservices without explicit architecture decision and measurable need.
  - Do not introduce full CQRS or full event sourcing by default.
  - Do not add abstraction layers with no current domain pressure.

### 4) Inter-domain Communication (mandatory)

- Allowed mechanisms only:
  - Formal query/service contract (sync request/response).
  - Orchestrator use case in application layer (multi-domain workflow coordination).
  - Domain events (internal first, explicit subscribers).
- Hard ban: no direct dependency on another domain's internal models, repositories, tables, or business rules.
- Hard ban: no uncontrolled cross-domain data access (including convenience SQL joins across domain ownership boundaries).
- When to use:
  - Query/service contract for deterministic reads/writes requiring immediate response.
  - Orchestrator use case for transactional or ordered workflows spanning multiple domains.
  - Domain events for decoupled side effects and eventual consistency.

### 5) Real-time Communication (controlled exception)

- Real-time is an exception, not the default transport; default remains request/response APIs.
- Recommended: operational notifications, collaborative presence, progress streams, low-latency dashboards.
- Not recommended: core CRUD orchestration, security-critical decisions, and primary audit persistence.
- All real-time features must use a dedicated module with standardized channel naming, auth, and message contracts.
- WebSocket consumers/handlers must delegate critical business behavior to application use cases.
- Every new real-time feature requires explicit business justification and documentation in the corresponding domain docs.

### 6) Complete Audit (mandatory cross-cutting)

- Audit is mandatory for auth events, sensitive reads/changes, and critical business operations.
- Minimum audit event contract:
  - `actor`, `timestamp`, `action`, `domain`, `resource`, `result`, `contextId/requestId`.
  - `ip` and `userAgent` when available.
  - `beforeState` and `afterState` when mutation context applies.
- Audit implementation guidance:
  - Explicit logging in use cases for critical operations.
  - Automated hooks for sensitive pathways.
- Audit storage must be append-only, access-restricted, and include masking/redaction for sensitive data.
- Definition of Done for critical operations must include audit verification.

### 7) Atomic/Granular Permissions (mandatory)

- Authorization base is atomic permissions, not coarse role names.
- Roles are permission bundles, not the source of truth.
- Contextual authorization must be enforced via policy modules/services.
- Central authorization service is required; ad-hoc role-string checks are prohibited as a security basis.
- Backend is security source of truth; frontend checks are UX gating only.

### 8) Database Strategy (integrity and safety first)

- Stage policy (non-contradictory baseline): SISEM runs on a single PostgreSQL engine/instance in early stages, with strict domain ownership and logical isolation now; physical DB separation is evaluated later with documented criteria.
- Every domain-owned schema/table must enforce integrity intentionally: PK/FK constraints, uniqueness, explicit nullability, and indexes aligned with real query patterns.
- Application services/use cases define transaction boundaries for critical workflows; avoid ad-hoc transaction control in transport layers.
- For concurrency hotspots, document and apply safe update patterns (`SELECT ... FOR UPDATE`, optimistic version checks, idempotency keys, or queue serialization) per use case.
- Keep operational state and audit/history stores separated by responsibility (transactional tables are not audit logs; audit/history is append-only and query-optimized for traceability).

### 9) Team Collaboration Standards (mandatory)

- Architecture standards docs are live artifacts: PRs that change behavior/boundaries must update affected docs in the same change.
- Domain ownership model is explicit: assign primary and secondary maintainers per domain for backend, frontend, DB, and docs.
- Use a single DoD baseline for all domains/slices; no local ad-hoc DoD variants.
- PR review must include architecture compliance gates, not just code-style/lint checks.

### 9.1) Git Workflow Enforcement (mandatory)

- Every implementation task MUST start on a new branch linked to the approved change identifier.
- Hard ban: no implementation work is allowed directly on `main`.
- Hard ban: direct pushes to `main` are prohibited.
- `main` integration is allowed only through Pull Requests with review and required checks.
- If an agent receives an implementation task while on `main`, it must stop, create/switch to a compliant branch, and only then continue implementation.
- After PR merge or PR closure without merge, delete the working branch locally and remotely unless explicit retention is documented.

### 10) Testing Strategy (risk-based)

- Use a risk-based pyramid: unit and service tests as base, integration/API tests for contracts and boundaries, E2E for critical user journeys.
- Mandatory priority coverage areas: security/authentication/authorization, audit traceability, critical clinical flows, state transitions, and concurrency-sensitive paths.
- Rule: critical features must include proportional automated coverage before merge (depth depends on risk and blast radius).

### 10.1) Strict TDD-First Governance (mandatory additive)

- Scope (mandatory): all NEW features, NEW functionalities, and LARGE refactors.
- Planning rule: implementation task lists must start with testing tasks (design + creation) before production code tasks.
- Execution rule: enforce Red -> Green -> Refactor cycle; tests must fail first, then pass with minimal implementation, then refactor with tests still passing.
- PR evidence rule: include test-first proof (initial failing tests, implementation progression, final passing state).
- Exception rule: if TDD cannot be applied, document explicit rationale, define compensating controls/tests, and obtain explicit approval in PR review.

### 11) System Evolution Strategy (stage-based)

- Stage 1: stabilize modular-monolith boundaries and domain ownership on shared PostgreSQL infrastructure.
- Stage 2: harden domain modules (performance, observability, reliability, security controls) while preserving contracts.
- Stage 3: evaluate extraction/physical separation only with evidence (SLO pressure, operational pain, compliance, or independent scaling need).
- Hard ban: no architecture changes driven by hype, preference, or trend without measurable need and documented decision.

### 12) Recommended Architectural Decision Synthesis

- Keep the modular monolith as the default system shape.
- Keep domain-first boundaries as the default planning and delivery unit.
- Keep DB-per-domain ownership on PostgreSQL as the mandatory data policy (logical first, physical by criteria).
- Keep centralized security/audit governance and contract-based inter-domain integration.

### 13) System Blueprint (canonical)

- Backend: Django/DRF layered by `presentation -> application -> domain -> infrastructure`, with use cases owning critical flows.
- Frontend: React domain-first structure where UI is transport/presentation and domain/application modules own behavior.
- Security: JWT in HttpOnly cookies + CSRF for mutating operations + centralized authorization policies.
- Audit: append-only, restricted, masked traceability store with required event contract.
- Communication: request/response by default; real-time as controlled exception; cross-domain via contracts/orchestrators/events only.

### 14) Risks to Avoid (reviewer anti-checklist)

- Pseudo-domain modularization (folders changed but dependencies and ownership remain tangled).
- Shared module sprawl that accumulates business decisions in `common`/`shared`/`utils`.
- Premature complexity (microservices/CQRS/event-sourcing without evidence).
- Dispersed security logic (authorization duplicated in views/components/helpers instead of centralized policies).

### 15) Final Recommendation (operational)

- Optimize for disciplined incremental evolution: enforce boundaries, integrity, and traceability first.
- Prefer measurable architecture decisions with explicit rollback plans over speculative redesigns.
- Treat docs/checklists as execution controls, not optional documentation.

### Pull Request Compliance Checklist (architecture)

- [ ] Layer responsibilities are respected (`presentation` vs `application` vs `domain` vs `infrastructure`).
- [ ] No critical business rules live in transport/UI utility code.
- [ ] Domain boundaries are explicit; no direct cross-domain data access.
- [ ] Pattern choices are justified (repository/events/policies/transactions).
- [ ] Inter-domain communication uses only approved mechanisms (contract/orchestrator/event).
- [ ] Real-time usage is justified, standardized, and delegated to use cases.
- [ ] Audit coverage exists for critical operations with minimum event contract.
- [ ] Authorization uses atomic permissions and centralized policies (no ad-hoc role strings).
- [ ] No premature complexity was introduced.
- [ ] DB changes document integrity constraints, transaction boundary, and concurrency strategy.
- [ ] Critical features include proportional automated tests by risk level.
- [ ] New features/new functionality/large refactors show TDD-first evidence (tests-first tasks + Red/Green/Refactor trace).
- [ ] Any TDD exception includes explicit rationale, compensating controls/tests, and reviewer approval.
- [ ] Architecture docs affected by boundary/flow changes were updated in the same PR.

### Canonical domain docs

- `docs/architecture/domain-map.md`
- `docs/architecture/context-map.md`
- `docs/architecture/dependency-rules.md`
- `docs/architecture/repo-navigation-map.md`
- `docs/architecture/db-ownership-migration-policy.md`
- `docs/guides/pr-merge-governance.md`
- `docs/guides/domain-dor-dod.md`
- `docs/guides/incremental-domain-migration.md`
- `docs/templates/rfc-cross-domain-template.md`

## Protocolo documental de reducción de incertidumbre (obligatorio)

Cuando una tarea implique diseño, implementación, refactor o decisiones con impacto de arquitectura/contratos, el agente DEBE usar `docs/` como sistema primario para reducir incertidumbre antes de proponer cambios.

### A) Mapa canónico de documentación (path + uso + trigger)

| Ruta | Para qué sirve | Cuándo consultarlo (trigger) |
| --- | --- | --- |
| `docs/architecture/hexagonal-clean-framework.md` | Reglas de Hexagonal/Clean y separación de responsabilidades | Diseño de arquitectura, refactor por capas, dudas de ubicación de lógica |
| `docs/governance/solid-enforcement.md` | Criterios operativos para enforcement de SOLID | Cambios de diseño interno, extracción de servicios, revisión de acoplamiento |
| `docs/architecture/pattern-catalog.md` | Cuándo usar/evitar patrones (use case, repository, event, policy, transaction) | Decisión de patrón o discusión de tradeoffs |
| `docs/architecture/backend-structure-reference.md` | Estructura backend objetivo por dominio/capa | Implementación backend o migración estructural |
| `docs/architecture/frontend-structure-reference.md` | Estructura frontend objetivo por dominio/capa | Implementación frontend o migración estructural |
| `docs/domains/auth-access/*` | Verdad de dominio auth/access (boundary, ACL, PRD, decisiones pendientes) | Cambios de auth, permisos, RBAC, boundary cross-domain |
| `docs/api/*` | Contratos API, estándares y módulos | Crear/modificar endpoints, payloads, errores, versionado |
| `docs/governance/*` | Reglas de gobierno, compliance y gates de entrega | Decisiones de riesgo, excepciones, calidad y controles |
| `docs/runbooks/*` | Procedimientos operativos y ejecución repetible | Operación, troubleshooting, handoff y tareas recurrentes |

> Si alguna ruta canónica esperada no existe en la rama actual, usar fallback inmediato: `docs/architecture/overview.md`, `docs/architecture/dependency-rules.md`, `docs/architecture/repo-navigation-map.md`, `docs/guides/pr-merge-governance.md`, `docs/guides/domain-dor-dod.md`, y documentar el gap en la PR.

### B) Playbooks por tipo de solicitud

- **Diseño de arquitectura**
  1. `docs/architecture/hexagonal-clean-framework.md`
  2. `docs/governance/solid-enforcement.md`
  3. `docs/architecture/pattern-catalog.md`
  4. `docs/architecture/context-map.md` + `docs/architecture/dependency-rules.md`
- **Implementación backend**
  1. `docs/architecture/backend-structure-reference.md`
  2. `docs/architecture/hexagonal-clean-framework.md`
  3. `docs/architecture/pattern-catalog.md`
  4. `docs/api/*` (si hay contrato) + `docs/domains/<dominio>/*`
- **Implementación frontend**
  1. `docs/architecture/frontend-structure-reference.md`
  2. `docs/architecture/hexagonal-clean-framework.md`
  3. `docs/architecture/pattern-catalog.md`
  4. `docs/api/*` (si consume contrato) + `docs/domains/<dominio>/*`
- **Cambios de API/contratos**
  1. `docs/api/standards.md`
  2. `docs/api/modules/*.md` afectados
  3. `docs/architecture/dependency-rules.md`
  4. `docs/domains/<dominio>/*` relacionado
- **Decisiones / riesgos / excepciones**
  1. `docs/governance/*`
  2. `docs/guides/pr-merge-governance.md`
  3. `docs/guides/domain-dor-dod.md`
  4. `docs/templates/rfc-cross-domain-template.md` (si cruza dominios)
- **Migración/refactor de dominio**
  1. `docs/architecture/domain-map.md`
  2. `docs/architecture/db-ownership-migration-policy.md`
  3. `docs/guides/incremental-domain-migration.md`
  4. `docs/domains/<dominio>/*` + RFC si hay impacto cross-domain

### C) Orden de lectura recomendado

- **Fast path (contexto mínimo, obligatorio antes de proponer cambios):**
  1. `docs/README.md`
  2. `docs/architecture/overview.md`
  3. Documento específico de tarea (`docs/api/*` o `docs/domains/<dominio>/*`)
  4. `docs/architecture/dependency-rules.md`
- **Deep path (si hay ambigüedad, impacto alto o cross-domain):**
  1. Fast path completo
  2. `docs/architecture/hexagonal-clean-framework.md`
  3. `docs/governance/solid-enforcement.md`
  4. `docs/architecture/pattern-catalog.md`
  5. `docs/architecture/backend-structure-reference.md` o `docs/architecture/frontend-structure-reference.md`
  6. `docs/governance/*` + `docs/runbooks/*`
  7. `docs/templates/rfc-cross-domain-template.md` si aplica

### D) Reglas de precedencia documental (si hay conflicto)

Orden de autoridad (de mayor a menor):

1. `AGENTS.md` más específico del subtree (incluye este root cuando no hay override).
2. Documentos de governance/compliance (`docs/governance/*`, `docs/guides/pr-merge-governance.md`).
3. Contratos explícitos (`docs/api/standards.md` + módulo específico).
4. Documentación de dominio (`docs/domains/<dominio>/*`).
5. Frameworks y referencias de estructura (`docs/architecture/*-framework.md`, `*structure-reference.md`, `pattern-catalog.md`).
6. Runbooks y guías operativas (`docs/runbooks/*`, `docs/getting-started/*`).

Si persiste contradicción:
- No inventar criterio propio.
- Elegir la opción más restrictiva para seguridad/auditoría.
- Abrir/actualizar RFC corto y dejar decisión explícita en PR.

### E) Checklist obligatorio antes de proponer cambios

- [ ] Identifiqué tipo de solicitud (arquitectura, backend, frontend, API, riesgo, migración).
- [ ] Ejecuté fast path completo.
- [ ] Ejecuté deep path si hay impacto alto, ambigüedad o cross-domain.
- [ ] Confirmé reglas de Hexagonal/Clean + SOLID + catálogo de patrones aplicables.
- [ ] Validé contrato de dominio/API afectado.
- [ ] Registré explícitamente supuestos y restricciones derivadas de docs.

### F) Checklist obligatorio antes de cerrar tarea / PR

- [ ] La descripción de PR lista documentos consultados con rutas concretas.
- [ ] La PR incluye sección "Evidencia documental" con: ruta, decisión tomada y impacto.
- [ ] Si hubo conflicto documental, la PR documenta precedencia aplicada y resolución.
- [ ] Si faltó un documento canónico esperado, la PR reporta gap y fallback utilizado.
- [ ] Se actualizó documentación impactada en el mismo cambio (si cambió behavior/boundary/contrato).
- [ ] Se verifica que no hubo cambios fuera de alcance en código de aplicación.

## Active Skills (SISEM)

| Skill | Recommended use | Path |
| --- | --- | --- |
| `vercel-react-best-practices` | React performance and refactoring patterns | `.opencode/skill/vercel-react-best-practices/SKILL.md` |
| `interface-design` | Create intentional UI layouts and visual hierarchy | `.opencode/skill/interface-design/SKILL.md` |
| `web-design-guidelines` | UI/UX and accessibility review against web guidelines | `.opencode/skill/web-design-guidelines/SKILL.md` |
| `typescript` | Types, interfaces, strict generics | `.opencode/skill/typescript/SKILL.md` |
| `tailwind-4` | Tailwind styling + `cn()` | `.opencode/skill/tailwind-4/SKILL.md` |
| `zod-4` | Schemas and validation (Zod v4) | `.opencode/skill/zod-4/SKILL.md` |
| `zustand-5` | Stores, slices, persistence | `.opencode/skill/zustand-5/SKILL.md` |
| `django-drf` | DRF endpoints, serializers, permissions, filters | `.opencode/skill/django-drf/SKILL.md` |
| `api-design-principles` | REST API contract and versioning design | `.opencode/skill/api-design-principles/SKILL.md` |
| `error-handling-patterns` | Error taxonomy, contracts, retries, fallback | `.opencode/skill/error-handling-patterns/SKILL.md` |
| `systematic-debugging` | Root-cause-first workflow for bugs and regressions | `.opencode/skill/systematic-debugging/SKILL.md` |
| `brainstorming` | Plan and scope features before implementation | `.opencode/skill/brainstorming/SKILL.md` |
| `pytest` | Python tests, fixtures, mocking | `.opencode/skill/pytest/SKILL.md` |
| `playwright` | E2E with Page Objects + MCP | `.opencode/skill/playwright/SKILL.md` |
| `pr-create-sisem` | PR creation with SISEM evidence-first structure | `.opencode/skill/pr-create-sisem/SKILL.md` |
| `pr-review-sisem` | PR review with SISEM governance + approve/squash actions | `.opencode/skill/pr-review-sisem/SKILL.md` |
| `find-skills` | Discover/install skills when requested | `.opencode/skill/find-skills/SKILL.md` |

## Auto-invoke Matrix

| Action | Skill |
| --- | --- |
| Create/modify React components (performance-aware) | `vercel-react-best-practices` |
| Create new UI screens/layout direction before implementation | `interface-design` |
| Review UI/UX/accessibility compliance | `web-design-guidelines` |
| Write TypeScript types | `typescript` |
| Tailwind styling | `tailwind-4` |
| Zod / RHF validation | `zod-4` |
| Create/edit global stores | `zustand-5` |
| Design Django/DRF APIs | `django-drf` |
| Design/review API contracts and standards | `api-design-principles` |
| Design/review error contracts, retries, and fallback behavior | `error-handling-patterns` |
| Debug bugs, test failures, and regressions | `systematic-debugging` |
| User asks for planning/discovery before coding | `brainstorming` |
| Backend Python tests | `pytest` |
| E2E tests | `playwright` |
| Create/open PR with standardized SISEM structure and evidence | `pr-create-sisem` |
| Review/audit PRs and decide approve/request-changes/squash | `pr-review-sisem` |
| User asks to discover/install skills | `find-skills` |

## Engram Protocol (Mandatory Repo Baseline)

This is the minimum required Engram protocol at repository level and applies even if local/global agent setup is missing or different.

### Session Start (before coding, when applicable)

- Review prior context before starting work on an existing topic/feature/bug.
- Use `mem_context` and/or `mem_search` on `project: SISEM_SHARED` before starting when prior team context may exist.
- Use `project: SISEM_LOCAL` only when you need your own local continuity.
- If `mem_search` returns a match, call `mem_get_observation` before acting on it (search results may be truncated).

### During Work (mandatory saves)

- Use `mem_save` immediately after high-signal events that matter to the team:
  - architecture/design decisions with cross-team impact
  - bug fixes with root cause and prevention notes
  - shared conventions/patterns that others must follow
  - config/environment changes that affect other developers
- Save shared items with `project: SISEM_SHARED` (this project is exported to `.engram/`).
- Save temporary/local notes with `project: SISEM_LOCAL` and `scope: personal`.
- Do not save routine low-value progress updates to `SISEM_SHARED`.

### Session Close (mandatory)

- Before ending the session, call `mem_session_summary` with goal, discoveries, accomplished work, next steps, and relevant files.

### Non-SDD `topic_key` Convention (mandatory)

- Reuse stable keys (upsert behavior) for ongoing work on the same topic to avoid duplicated observations.
- Create new keys only when the topic actually changes.
- Required key patterns:
  - `feature/{slug}/decision`
  - `feature/{slug}/progress`
  - `bug/{id-or-slug}/fix`
  - `ops/{area}/config`
  - `docs/{topic}/note`

### Operational Checklist

- Start: `mem_context`/`mem_search` on `SISEM_SHARED`; check `SISEM_LOCAL` only if needed.
- During: `mem_save` to `SISEM_SHARED` only for high-signal team decisions; keep local noise in `SISEM_LOCAL`.
- Search safety: after `mem_search`, use `mem_get_observation` for full content.
- Close: `mem_session_summary` before handing off or ending the session.

### Team Sync Automation

- One-time per clone: run `./.engram/scripts/install-hooks.sh`.
- `commit-msg` hook auto-exports shared memory via `engram sync --project SISEM_SHARED` and stages `.engram/` updates.
- `post-merge`, `post-checkout`, and `post-rewrite` hooks auto-import with `engram sync --import`.

### Git Hooks Automation

- The project uses repo hooks from `.githooks/`.
- `commit-msg` hook auto-exports shared memory via `engram sync --project SISEM_SHARED` and stages `.engram/` updates.
- `post-merge`, `post-checkout`, and `post-rewrite` hooks auto-import with `engram sync --import`.

## Backend Guardrails

- Keep clean architecture: presentation (views/serializers), use_cases, infrastructure, domain.
- JWT must stay in HttpOnly cookies.
- CSRF must be enforced via `X-CSRF-TOKEN` for mutating requests.
- Data ownership rule: each domain owns its PostgreSQL data model and migrations.
- Data access rule: no direct cross-domain table/schema reads or writes from application code.

## Docker-First Testing Rule (mandatory)

- When an agent needs to run tests/validation, it MUST start and use required services via Docker (`docker compose`).
- Hard ban: do not start backend/frontend/supporting services directly on the host machine for test execution.
- Preferred flow: `docker compose up -d` for dependencies/services, run test commands in containerized context, then inspect logs with `docker compose logs -f` if needed.
- Any exception to Docker-first test execution must be explicitly approved by the user in the same thread.

## Development Commands

### Frontend (pnpm)
```bash
pnpm dev
pnpm lint
pnpm test
```

### Backend (Django)
```bash
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

### Docker (recommended)
```bash
docker compose up --build
docker compose down
# use down -v only for explicit data reset
docker compose logs -f
```
