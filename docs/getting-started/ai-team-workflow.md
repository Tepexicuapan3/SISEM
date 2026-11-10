# Flujo IA del Equipo (SDD-Orchestrator + Engram)

> TL;DR: En SISEM, el flujo oficial de delivery es SDD-Orchestrator + Engram + PR. Jira ya no se usa (`docs/governance/decision-sin-jira.md`). El trabajo se planifica y ejecuta por dominio completo, con ownership explicito y gates de calidad antes de merge.

## Problem / Context

Sin un proceso unificado, se pierde trazabilidad, se duplican decisiones y aparecen PRs que rompen boundaries entre dominios.

## Solution / Implementation

## Arquitectura operativa

```text
Persona
  -> SDD-Orchestrator (explore/propose/spec/design/tasks/apply/verify)
  -> Implementacion por dominio
  -> Engram (memoria compartida high-signal)
  -> PR/Merge
```

## Reglas obligatorias

1. Dominio primero (backend + frontend + DB + docs).
2. Estrategia de datos: DB por dominio con PostgreSQL target.
3. Sin SQL cross-domain desde codigo de aplicacion.
4. Cross-domain changes requieren RFC corto y checklist de impacto.
5. No big-bang cutover; usar estados `legacy`, `hybrid`, `domain-first`.
6. Para NEW feature/NEW functionality/LARGE refactor, TDD-first es obligatorio (tasking de tests primero + Red -> Green -> Refactor).

## Protocolo diario

### Inicio

1. Validar el alcance del cambio y el dominio owner.
2. Traer contexto en Engram (`SISEM_SHARED`).
3. Ejecutar fase SDD segun alcance (`/sdd-new`, `/sdd-continue`, `/sdd-apply`).

### Durante

1. Ejecutar trabajo por slices chicos.
2. Arrancar cada slice aplicable con test fallando (Red), luego implementacion minima (Green) y refactor seguro.
3. Guardar en Engram solo eventos high-signal (decisiones de arquitectura/tecnicas, bugfix raiz, convenciones, config).
4. Mantener el estado del cambio en SDD/Engram y en el PR.

### Antes de PR

1. Verificar hooks activos.
2. Revisar cambios por dominio.
3. Validar checklist de dependencia, datos y seguridad.
4. Adjuntar evidencia TDD-first cuando aplique (fallo inicial + progresion + verde final) o excepcion aprobada con controles compensatorios.

### Gate de commit (hooks)

En cada `git commit` se mantiene esta automatizacion:

1. `commit-msg` ejecuta `.engram/scripts/export-on-commit-msg.sh` y sincroniza `SISEM_SHARED` en `.engram/`.

El `pre-commit` se mantiene sin validaciones bloqueantes adicionales en este proyecto.

Importante: los hooks en `.githooks/` automatizan hygiene/sync local de Engram; no reemplazan CI/CD ni branch protection de PR.

### Cierre de PR

1. Vincular el cambio SDD.
2. Declarar dominios impactados y estado (`legacy`/`hybrid`/`domain-first`).
3. Adjuntar RFC si hay impacto cross-domain.

## Engram (convencion minima)

- Proyecto compartido: `SISEM_SHARED`.
- Proyecto local: `SISEM_LOCAL`.

### Cuando guardar decisiones tecnicas/arquitectura

Guardar en `SISEM_SHARED` cuando haya impacto reutilizable para el equipo:

- Decision de arquitectura o trade-off cross-domain.
- Cambio de politica tecnica (errores, contratos, ownership de datos, seguridad operativa).
- Fix de bug con causa raiz no obvia.
- Convencion nueva que otros dominios deben respetar.

Usar formato:

- `What`: que decision/cambio se tomo.
- `Why`: por que se tomo.
- `Where`: archivos/rutas impactadas.
- `Learned`: riesgo, edge case o criterio operativo.

### Topic keys recomendados

- `feature/{slug}/decision`
- `feature/{slug}/progress`
- `bug/{id-or-slug}/fix`
- `ops/{area}/config`
- `docs/{topic}/note`

Ejemplos concretos:

- `feature/auth-domain/decision` para un cambio de contrato auth entre dominios.
- `feature/repo-operating-model/progress` para ajustar hooks/flujo operativo.
- `ops/postgresql-domain-ownership/config` para reglas de ownership y migraciones.

## Verificaciones rapidas

```bash
git config --get core.hooksPath
ls .githooks
```

## References

- `AGENTS.md`
- `docs/guides/pr-merge-governance.md`
- `docs/guides/domain-dor-dod.md`
- `docs/guides/incremental-domain-migration.md`
- `docs/getting-started/engram-team-sync.md`
- `docs/domains/auth-access/jira-workflow-operating-model.md` (histórico)
