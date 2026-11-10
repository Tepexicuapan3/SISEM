# Domain DoR / DoD

> TL;DR: Un dominio entra al sprint solo con requisitos minimos (DoR) y se considera cerrado cuando cumple Definition of Done transversal.

## Problem / Context

La migracion por dominios falla si no hay criterio comun para empezar y terminar trabajo.

## Solution / Implementation

## Definition of Ready (DoR)

- Dominio y ownership definidos (backend/frontend/DB/docs).
- Owners primario y secundario asignados por area (backend/frontend/DB/docs).
- Alcance limitado al slice vertical de negocio.
- Contratos API o cambios de datos identificados.
- Riesgos y dependencias externas listadas.
- Alcance y criterios de aceptación definidos (cambio SDD o descripción del PR).
- Cambio SDD creado (o justificacion explicita de por que no aplica).
- Para NEW feature/NEW functionality/LARGE refactor: tasking inicial de testing definido (tests-first por riesgo).

### DoR adicional para auth-access (KAN-55)

- Slice clasificado como `P0|P1|P2` con justificación por factores (`auth/session`, `policy`, `audit`, `mutation`, `cross-domain`).
- Mínimos de cobertura esperados por riesgo declarados antes de iniciar apply.
- Si hay excepción TDD propuesta, debe existir borrador de `TddExceptionRecord` con aprobador objetivo.

## Definition of Done (DoD)

- Backend y frontend del slice funcionando en entorno local.
- Seguridad respetada (JWT cookies HttpOnly, CSRF en mutaciones).
- Docs actualizadas (mapa, migracion, governance si aplica).
- Features criticas con cobertura automatizada proporcional al riesgo (unit/service, integration/API, E2E segun impacto).
- Para NEW feature/NEW functionality/LARGE refactor: evidencia TDD-first (Red -> Green -> Refactor) anexada en tareas/PR.
- Toda excepcion TDD documentada con racional explicito + controles compensatorios + aprobacion en el PR.
- Engram actualizado con decisiones/fixes relevantes (`SISEM_SHARED`).
- Hooks Git requeridos activos y sincronizacion de Engram operativa.
- PR mergeable con checklist completo y reviewers correctos.

### DoD adicional por riesgo (KAN-55)

| Riesgo | Evidencia mínima para DoD |
|---|---|
| P0 | Red->Green->Refactor completo + >=2 integration/API + >=1 E2E crítico + validación de auditoría/requestId |
| P1 | Red->Green->Refactor completo + >=1 integration/API + validación de contratos afectados |
| P2 | Red->Green->Refactor completo + unit/service de comportamiento modificado |

Regla: evidencia incompleta para su nivel de riesgo => DoD rechazado.

## DoD extendido para dominio piloto cerrado

- Estado del dominio pasa a `domain-first` o queda `hybrid` con backlog claro.
- Dependencias cross-domain documentadas y aprobadas.
- Plan de siguientes slices registrado.

## References

- `docs/architecture/domain-map.md`
- `docs/guides/incremental-domain-migration.md`
- `docs/guides/pr-merge-governance.md`
- `docs/getting-started/ai-team-workflow.md`
