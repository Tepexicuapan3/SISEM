# PR / Merge Governance (Domain-First)

> TL;DR: PRs chicos, trazables y alineados a dominio. Nada de merges opacos, ni cambios cross-domain sin control, ni cambios de datos sin ownership y plan de migracion a PostgreSQL.

## Problem / Context

Sin governance, el trabajo paralelo genera colisiones, retrabajo y deuda tecnica silenciosa.

## Solution / Implementation

## Reglas de PR

1. Una intencion principal por PR.
2. Alcance y criterios de aceptación en la descripción del PR (o el cambio SDD). Jira ya no se usa (`docs/governance/decision-sin-jira.md`).
3. Referencia obligatoria al cambio SDD.
4. Indicar dominio(s) impactado(s) y estado (`legacy`, `hybrid`, `domain-first`).
5. Si cruza dominios, adjuntar RFC corto usando template.
6. No mezclar refactor de estructura con cambios funcionales grandes sin justificacion.
7. Si hay impacto de datos, detallar ownership de dominio, etapa de migracion (`expand/migrate/contract`) y riesgo operativo.
8. Si cambia boundaries/flujo arquitectonico, actualizar docs impactados en el mismo PR (estandares vivos).
9. Incluir owners primario/secundario por dominio impactado (backend, frontend, DB, docs) en descripcion o checklist del PR.
10. Para NEW feature/NEW functionality/LARGE refactor, aplicar TDD-first estricto: tasks de testing primero y ciclo Red -> Green -> Refactor.

## Workflow obligatorio de branch y PR

- Cada developer crea una rama NUEVA por ticket partiendo desde `main` actualizado.
- Todo el trabajo del ticket ocurre solo en esa rama (sin mezclar multiples tickets en la misma rama).
- Cuando el ticket esta completo y testeado, se abre PR hacia `main`.
- Los cambios en `main` se integran unicamente via PR (sin pushes directos).
- La rama del ticket se elimina al hacer merge o al cerrar el PR sin merge.

### Convencion de nombres de rama

- Formato recomendado: `<tipo>/<dominio>/<slug>`.
- Tipos permitidos: `feat`, `fix`, `chore`.
- Ejemplos:
  - `feat/auth/KAN-142-jwt-refresh-rotation`
  - `fix/consulta/KAN-287-validacion-receta`
  - `chore/docs/KAN-310-ajuste-pr-governance`

## Gates minimos de merge

- Checklist de seguridad (JWT HttpOnly + CSRF para mutaciones).
- Validacion de reglas de dependencia (`docs/architecture/dependency-rules.md`).
- Evidencia de testing relevante (sin necesidad de build completo en docs-only PR).
- Evidencia de testing proporcional al riesgo para features criticas (unit/integration/API/E2E segun impacto).
- En frontend, reportar typecheck split como gates separados (`typecheck:app`, `typecheck:tests`, `typecheck:e2e` y `typecheck:bun`).
- En frontend, adjuntar evidencia negativa automatizada de detección de deuda TS (`test:guard:ts-debt-detection`) para evitar falsos verdes de typecheck.
- En frontend, adjuntar enforcement automatizado anti-bypass (`test:guard:ts-anti-bypass`) contra `any`, `as unknown as`, `@ts-ignore` y `@ts-nocheck` en fronteras críticas de tests.
- Si hay cambios de contrato auth/frontend, incluir evidencia de `src/test/integration/contracts/auth-contract-alignment.spec.ts`.
- Gate CI contractual obligatorio para auth: job `auth-contract-governance` (backend `test_auth_api` + `test_auth_contract_edges`, frontend `auth-contract-alignment`, `typecheck:app`, `typecheck:tests`).
- Smoke E2E de cierre se valida en Docker con preflight reproducible (`bun run test:e2e:bootstrap`, `bun run test:e2e:smoke` / `test:e2e:kan4`); ejecucion host-only no cuenta como evidencia final.
- Para hardening de aliases/frontend structure, incluir guard automatizado ejecutable contra reintroduccion de aliases legacy (`bun run test:guard:legacy-alias`).
- Evidencia test-first cuando aplique TDD estricto: fallo inicial, progresion de implementacion y estado final en verde.
- Si hubo excepcion TDD, incluir racional explicito, controles/tests compensatorios y aprobacion registrada en el PR.
- Confirmacion de actualizacion de docs cuando cambia la operativa.
- Evidencia de memoria high-signal guardada en Engram (`SISEM_SHARED`) cuando corresponda.
- Cuando se reporte evidencia Engram, incluir `topic_key` estable segun convencion (`feature/{slug}/decision`, `feature/{slug}/progress`, `bug/{id-or-slug}/fix`, `ops/{area}/config`, `docs/{topic}/note`).
- Hooks Git requeridos activos y sincronizacion de Engram operativa.
- Checklist de datos completo: ownership por dominio en PostgreSQL, sin SQL cross-domain directo, y plan de rollback en cambios de alto riesgo.

### Gate explicito KAN-55: TDD-first por riesgo (auth-access)

Aplica a cualquier PR/slice de `auth-access` en alcance KAN-52/KAN-56+.

Reglas go/no-go:
- [ ] Slice clasificado como `P0|P1|P2` con justificacion factor-a-factor.
- [ ] Evidencia Red->Green->Refactor completa segun `tdd-evidence-templates.md`.
- [ ] Minimos por riesgo cumplidos:
  - `P0`: >=2 integration/API + >=1 E2E crítico + tests de reglas críticas.
  - `P1`: >=1 integration/API + tests core.
  - `P2`: tests unit/service para comportamiento modificado.
- [ ] Guardrails no negociables verificados (sin role-string ad-hoc, sin cross-domain directo, sin breaking API no versionado).
- [ ] Contrato de trazabilidad/auditoría verificado (`X-Request-ID` + error `requestId` + evento de auditoría mínimo).

Condiciones de bloqueo automático:
- Falta evidencia RED inicial.
- Evidencia incompleta para el riesgo declarado.
- Excepción TDD incompleta o sin aprobación requerida.
- Persistencia de conflictos documentales en `docs/domains/auth-access/*` (merge markers).

### Gate explicito: Auth-access contract alignment (obligatorio cuando aplica)

Aplica a PRs que toquen alguno de estos artefactos en auth-access:
- backend auth payload/contract (`build_auth_user`, views/auth responses, tests de contrato)
- `docs/api/modules/auth.md`
- `frontend/src/api/types/auth.types.ts`

Checklist obligatorio de alineacion:
- [ ] `docs/api/modules/auth.md` actualizado contra runtime real.
- [ ] `frontend/src/api/types/auth.types.ts` actualizado contra runtime real.
- [ ] No missing fields between backend runtime contract, docs/api/modules/auth.md, and frontend/src/api/types/auth.types.ts.
- [ ] Tabla de error codes revisada contra tests/runtime actuales (sin inventar codigos nuevos).
- [ ] Declaracion explicita de compatibilidad hacia atras (sin breaking changes involuntarios).
- [ ] `docs/domains/auth-access/pending-decisions.md` revisado y con evidencia/estado actualizado para items impactados.

## Collaboration baseline (obligatorio)

- Estandares de arquitectura y governance se tratan como artefactos vivos; no se difieren updates de docs a "PR posterior".
- DoD de dominio es unico y se evalua con la misma base en todo el repo.
- Review de arquitectura no es opcional: PRs con impacto de boundaries/flows requieren validacion explicita de compliance (no solo lint/format).

## Checklist de impacto de datos/migraciones

- Dominio owner de datos identificado.
- Tablas/schemas/migraciones afectados documentados.
- Cumple estrategia `DB por dominio` (PostgreSQL target).
- No hay acceso SQL directo a tablas/schemas de otro dominio.
- Controles de sobrecarga evaluados (particionado, indices, retencion/archivo, read-models/reporting, observabilidad).
- Criterio de paso logico -> fisico evaluado (si aplica).
- Rollback y monitoreo post-merge definidos.

## Convencion de labels sugerida

- `type:feature`, `type:fix`, `type:docs`, `type:chore`
- `domain:recepcion`, `domain:somatometria`, `domain:consulta`, `domain:auth`
- `status:legacy`, `status:hybrid`, `status:domain-first`

## References

- `.github/pull_request_template.md`
- `docs/architecture/db-ownership-migration-policy.md`
- `docs/templates/rfc-cross-domain-template.md`
- `docs/guides/domain-dor-dod.md`
- `docs/getting-started/ai-team-workflow.md`
