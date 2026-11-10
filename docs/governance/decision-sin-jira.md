# Decisión: Jira ya no se usa

> Vigente desde el 2026-11-10. Reemplaza toda regla que exigía ticket, épica o
> aprobación en Jira.

## Qué cambia

SISEM deja de usar Jira para planear y dar trazabilidad. Ningún PR, rama,
excepción de TDD ni checklist de DoR/DoD exige un ticket de Jira.

## Qué lo reemplaza

| Antes (Jira) | Ahora |
|---|---|
| Ticket o épica con alcance y criterios de aceptación | La propuesta o especificación del cambio (SDD) o la descripción del PR, con el alcance y los criterios de aceptación |
| Rama `<tipo>/<dominio>/<jira-key>-<slug>` | Rama `<tipo>/<dominio>/<slug>`, con el nombre del cambio aprobado |
| Título del PR con `[KAN-XXX]` | Título en conventional commits, sin clave |
| Aprobación de una excepción de TDD en Jira/PR | Aprobación en la revisión del PR |
| Seguimiento del estado en columnas de Jira | Estado del cambio en SDD/Engram y en el PR |

El resto del flujo no cambia: SDD, TDD primero, Engram, PR con revisión a
`main` y documentación actualizada en el mismo cambio.

## Qué no se toca

- La evidencia histórica que menciona tickets (`docs/domains/auth-access/kan-*`,
  `changelog.md`, `decision-log.md`, `docs/guides/kan-74-*`) queda como está:
  registra lo que pasó en su momento.
- `docs/domains/auth-access/jira-workflow-operating-model.md` queda como
  referencia histórica; ya no es un procedimiento vigente.
- Los skills `jira-epic` y `jira-task` quedan deprecados (no se invocan).
