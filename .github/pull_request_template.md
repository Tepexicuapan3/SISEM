## What and Why

- What changed:
- Why this change is needed:

## Domain Impact

- Primary domain:
- Domain status: `legacy` | `hybrid` | `domain-first`
- Additional domains impacted (if any):

## Data Impact (required if DB/schema/query changes)

- Data owner domain:
- PostgreSQL target impact (`expand` | `migrate` | `contract` | `N/A`):
- Cross-domain SQL access introduced?: `no` (required) / explain exception:
- Overload controls reviewed (partitioning, indexes, retention/archive, read-models, observability):
- Criteria logical -> physical isolation evaluated?:

## SDD Traceability

- SDD change (if applies):
- SDD phase status (`proposal/spec/design/tasks/apply/verify`):
- RFC cross-domain (required if multi-domain):
- Engram evidence (topic_key or note):

## TDD-First Evidence (required for NEW feature / NEW functionality / LARGE refactor)

- Scope applies?: `yes` / `no` (if `no`, explain why):
- Tests-first planning/tasks link or excerpt (prove tests were planned before implementation):
- RED evidence (initial failing test):
- GREEN evidence (minimal implementation passing):
- REFACTOR evidence (cleanup with tests still passing):
- Exception (if applicable): rationale + compensating controls/tests + approval (PR reviewer):

## KAN-55 Risk Gate (required for auth-access slices)

- Slice identifier (`S0..S6` if applies):
- Risk level (`P0` | `P1` | `P2`):
- Risk factor justification (auth/session, policy, audit, mutation, cross-domain):
- Minimum evidence required for selected risk:
- Go/No-Go result:

## Checklist

- [ ] Scope is focused and single-purpose
- [ ] SDD traceability completed (if applies)
- [ ] Security guardrails reviewed (JWT HttpOnly + CSRF in mutating flows)
- [ ] Dependency rules respected (`docs/architecture/dependency-rules.md`)
- [ ] Data ownership respected (`DB por dominio`) and PostgreSQL target considered
- [ ] No direct cross-domain table/schema access from application code
- [ ] Data migration/rollback plan documented for high-risk changes
- [ ] Docs updated if behavior or operation changed
- [ ] Engram high-signal decisions/fixes saved to `SISEM_SHARED`
- [ ] Tests/evidence attached (or N/A explained)
- [ ] TDD-first evidence included for applicable scope (tests-first plan + Red/Green/Refactor)
- [ ] Any TDD exception includes rationale, compensating controls/tests, and explicit approval
- [ ] (auth-access) KAN-55 risk gate completed (risk classification + minimum evidence by risk)
- [ ] (auth-access) No unresolved merge markers in `docs/domains/auth-access/*`

## Risks and Rollback

- Main risks:
- Rollback plan:
