## What and Why

- What changed:
  - [ ] {cambio 1}
  - [ ] {cambio 2}
- Why this change is needed:
  - {justificación de negocio/técnica}

## Domain Impact

- Primary domain: `{domain}`
- Domain status: `legacy` | `hybrid` | `domain-first`
- Additional domains impacted (if any):
  - {domain or `none`}

## Data Impact (required if DB/schema/query changes)

- Data owner domain: `{domain-owner}`
- PostgreSQL target impact (`expand` | `migrate` | `contract` | `N/A`):
  - {value + rationale}
- Cross-domain SQL access introduced?: `no` (required) / explain exception:
  - {evidence}
- Overload controls reviewed (partitioning, indexes, retention/archive, read-models, observability):
  - {evidence or `N/A` with reason}
- Criteria logical -> physical isolation evaluated?:
  - {yes/no + rationale}

## SDD Traceability

- SDD change (if applies): `{change-id}` or `N/A`
- SDD phase status (`proposal/spec/design/tasks/apply/verify`):
  - {status}
- RFC cross-domain (required if multi-domain):
  - {link/path} or `N/A`
- Engram evidence (topic_key or note):
  - `{topic_key}`

## TDD-First Evidence (required for NEW feature / NEW functionality / LARGE refactor)

- Scope applies?: `yes` / `no` (if `no`, explain why):
  - {rationale}
- Tests-first planning/tasks link or excerpt (prove tests were planned before implementation):
  - {link/evidence}
- RED evidence (initial failing test):
  - {command + failing output reference}
- GREEN evidence (minimal implementation passing):
  - {command + passing output reference}
- REFACTOR evidence (cleanup with tests still passing):
  - {what changed + proof}
- Exception (if applicable): rationale + compensating controls/tests + approval (PR reviewer):
  - {details or `N/A`}

## KAN-55 Risk Gate (required for auth-access slices)

- Slice identifier (`S0..S6` if applies): `{slice}` or `N/A`
- Risk level (`P0` | `P1` | `P2`): `{risk}` or `N/A`
- Risk factor justification (auth/session, policy, audit, mutation, cross-domain):
  - {justification}
- Minimum evidence required for selected risk:
  - {evidence list}
- Go/No-Go result:
  - `{GO|NO-GO}`

## Evidence Matrix (mandatory)

| Ruta | Decisión aplicada | Impacto en este PR |
| --- | --- | --- |
| `docs/guides/pr-merge-governance.md` | {regla aplicada} | {impacto} |
| `docs/architecture/dependency-rules.md` | {regla aplicada} | {impacto} |
| `{otra ruta canónica}` | {regla aplicada} | {impacto} |

## Checklist

- [ ] Scope is focused and single-purpose
- [ ] SDD traceability completed (if applies)
- [ ] Security guardrails reviewed (JWT HttpOnly + CSRF in mutating flows)
- [ ] Dependency rules respected (`docs/architecture/dependency-rules.md`)
- [ ] Data ownership respected (`DB por dominio`) and PostgreSQL target considered
- [ ] No direct cross-domain table/schema access from application code
- [ ] Data migration/rollback plan documented for high-risk changes
- [ ] Docs updated if behavior or operation changed
- [ ] Engram high-signal decisions/fixes saved to `SIRES_SHARED`
- [ ] Tests/evidence attached (or N/A explained)
- [ ] TDD-first evidence included for applicable scope (tests-first plan + Red/Green/Refactor)
- [ ] Any TDD exception includes rationale, compensating controls/tests, and explicit approval
- [ ] (auth-access) KAN-55 risk gate completed (risk classification + minimum evidence by risk)
- [ ] (auth-access) No unresolved merge markers in `docs/domains/auth-access/*`

## Risks and Rollback

- Main risks:
  - {risk 1}
  - {risk 2}
- Rollback plan:
  - {step-by-step rollback}

## Validation Commands Executed

- `{command}` -> `{result}`
- `{command}` -> `{result}`

## Notes for Reviewers

- Focus areas requested:
  - {focus 1}
  - {focus 2}
- Out of scope (explicit):
  - {items}
