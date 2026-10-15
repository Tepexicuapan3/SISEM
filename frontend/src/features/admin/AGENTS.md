# AGENTS.md - Admin Feature Ruleset

## Scope

- Applies to `frontend/src/features/admin/**`.
- If there is a conflict with `frontend/src/features/AGENTS.md`, this file wins.
- Keep structural parity with `frontend/src/features/auth/` for queries/mutations.

## Skills Reference

- `vercel-react-best-practices` - admin component performance and refactors.
- `interface-design` - admin layout/flow design before implementation.
- `web-design-guidelines` - UX/accessibility audits.
- `typescript` - strict typing for contracts and UI.
- `zod-4` - form/contract validation.
- `error-handling-patterns` - consistent error and fallback states.
- `systematic-debugging` - root-cause debugging.
- `brainstorming` - planning before large features.
- `find-skills` - discover/install skills when requested.

## Auto-invoke Skills

| Action | Skill |
| --- | --- |
| Create/refactor admin components | `vercel-react-best-practices` |
| Define admin layout/flow before coding | `interface-design` |
| Review admin UX/accessibility | `web-design-guidelines` |
| Define types/contracts | `typescript` |
| Implement validations | `zod-4` |
| Design error/fallback behavior | `error-handling-patterns` |
| Debug admin regressions | `systematic-debugging` |
| User asks to plan before implementation | `brainstorming` |
| User asks to discover/install skills | `find-skills` |

## Rules

- Do not use adapters for RBAC payload shape: backend already returns camelCase per `docs/api/modules/rbac.md`.
- Keep queries and mutations separated by module with dedicated keys.
- UI must not execute direct HTTP calls; use hooks backed by `api/resources`.
- Put reusable components in `shared/`; keep module-specific pieces in `modules/<module>/`.
- For catalogs, separate by catalog in `modules/catalogos/<catalog>/`.
- If permission is missing for secondary catalogs (roles/permissions), show a neutral contextual notice (not a red critical banner) and avoid exposing technical permission codes.
- Disable only dependent controls for that catalog and keep already-loaded data visible.
- Prevent unnecessary unauthorized calls by using `enabled: false` in queries.
- Resolve write-action permissions through `usePermissionDependencies()` to enforce declared dependencies.
- If a module requires composed permissions (e.g. edit + catalogs), model it as a dependency in `permission-dependencies.ts` instead of ad-hoc component checks.
- For buttons/routes that must enforce full dependencies, use `dependencyAware` mode in `PermissionGate` or `ProtectedRoute`.

## Architecture Guardrails

- Treat `pages/` and `components/` as presentation-only layers.
- Keep business and authorization decisions in `domain/` and permission dependency modules.
- Keep orchestration in `queries/` and `mutations/`; avoid embedding flow logic in JSX.
- Hard ban: critical business logic in generic helpers or UI utility files.

## Part 2 Guardrails (Operational)

- Admin cross-domain coordination must use explicit contracts/adapters/events; avoid direct dependency on internals of other domains.
- Real-time is exceptional; any channel/subscription logic must stay in adapters and delegate business decisions to `domain/`, `queries/`, or `mutations/`.
- Sensitive admin actions must preserve backend audit traceability (include request correlation metadata when available).
- Client-side checks are UX gating only; atomic permissions and centralized policies in backend decide authorization.

## Part 3 Guardrails (Operational)

- Assume backend staged DB policy in admin contracts: single operational PostgreSQL source now, strict domain ownership/logical isolation, physical split later by criteria; never design admin UX around cross-domain DB shortcuts.
- Keep collaboration/DoD discipline: when admin permissions, ownership boundaries, or critical flows change, update module docs and governance references in the same PR.
- Apply risk-based test depth: prioritize permission dependencies, degraded-access UX, sensitive mutations, and race-prone list/detail updates.
- Follow stage-based evolution: incremental module hardening over rewrite; no architecture jumps by preference.
- Top risks: role-string security drift in UI, hidden business rules in helpers, and missing coverage on critical admin paths.

## Capability map (v1)

- Users:
  - `admin.users.read` -> `admin:gestion:usuarios:read`
  - `admin.users.create` -> `admin:gestion:usuarios:create`
  - `admin.users.update` -> `admin:gestion:usuarios:update`
  - `admin.users.rolesCatalog.read` -> `admin:gestion:roles:read`
  - `admin.users.permissionsCatalog.read` -> `admin:gestion:permisos:read`
  - `admin.users.editFull` -> `usuarios:read + usuarios:update + roles:read + permisos:read`
- Roles:
  - `admin.roles.read` -> `admin:gestion:roles:read`
  - `admin.roles.create` -> `admin:gestion:roles:create`
  - `admin.roles.update` -> `admin:gestion:roles:update`
  - `admin.roles.delete` -> `admin:gestion:roles:delete`
  - `admin.roles.permissionsCatalog.read` -> `admin:gestion:permisos:read`
  - `admin.roles.editFull` -> `roles:read + roles:update + permisos:read`
- Catalogs:
  - `admin.catalogs.areas.*` -> `admin:catalogos:areas:*`
  - `admin.catalogs.centers.*` -> `admin:catalogos:centros_atencion:*`

## Checklist for New Admin Modules

1) Define domain capability keys (no ad-hoc checks in components).
2) Add backend requirement (`CAPABILITY_REQUIREMENTS`) and explicit dependencies when needed. MANDATORY: `admin.` is a strict prefix, so any `admin.*` key missing in the backend blocks the screen for everyone, admin included (the fallback requirement is ignored). Full checklist: `docs/domains/auth-access/permissions-source-of-truth.md` section 10; guarded by `backend/apps/authentication/tests/test_capability_registry_sync.py`.
3) Consume capability in pages/dialogs (`usePermissionDependencies`).
4) Protect catalog queries with `enabled: false`.
5) Implement missing-access UX state (neutral notice + selective disable).
6) Cover capability/dependency behavior with unit/integration tests.
7) Keep cross-domain interactions on explicit contracts (no internal cross-domain coupling).
8) If using realtime, keep handler logic non-critical and delegated.
9) Verify sensitive flows keep audit correlation metadata.
10) Add proportional automated coverage for critical paths (permissions, sensitive writes, degraded access).
11) Update docs/DoD references in the same PR when boundaries or contracts change.

## Module Structure

Each submodule should follow this base structure:

```txt
pages/
components/
queries/
mutations/
domain/
utils/
```

## Current Catalogs

- `centros-atencion`
- `areas`
