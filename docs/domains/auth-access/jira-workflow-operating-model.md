# Auth-Access — Jira Workflow Operativo (histórico)

> **Ya no se usa.** Desde el 2026-11-10 SISEM no usa Jira (`docs/governance/decision-sin-jira.md`). Este documento queda como referencia de cómo se trabajó.

> TL;DR: Para Auth-Access usamos un único flujo de columnas en Jira con gates claros por estado, lanes por tipo de trabajo (no por columna), evidencia TDD/integración/PR y reglas explícitas para humanos y agentes IA.

## Problem / Context

Sin un workflow operativo explícito, el tablero se usa como “lista de tareas sueltas” y se pierde señal de riesgo real: DoR incompleto, TDD sin evidencia, bloqueos sin dueño/ETA y cierres sin compliance.

## Solution / Implementation

## 1) Flujo aprobado (columnas)

Orden base:

`Backlog Sprint -> Ready (DoR OK) -> In Dev (Red->Green) -> In Test (Integración/E2E + evidencia) -> In Review (PR + compliance) -> Blocked -> Done`

Estado transversal:

- `Blocked` se puede usar desde cualquier estado operativo cuando hay dependencia externa o impedimento real.

Regla dura:

- **No usar columnas para “tareas de control” o “tareas puntuales”.**
- La clasificación operativa va por **swimlane/label**.

## 2) Swimlanes/labels oficiales

- `lane:standard`
- `lane:ops-control`
- `lane:expedite` (**WIP = 1**, **SLA <= 24h**)

Uso esperado:

- `lane:standard`: trabajo normal del sprint.
- `lane:ops-control`: controles operativos/compliance/runbook sin mezclar con la lane estándar.
- `lane:expedite`: urgencia real; solo una activa por vez.

## 3) Reglas por columna (entrada/salida)

| Columna | Propósito | Entrada (mínimo) | Salida (mínimo) |
| --- | --- | --- | --- |
| `Backlog Sprint` | Cola priorizada del sprint | Ticket con objetivo, owner y lane definida | Priorización confirmada + owner/secondary claros |
| `Ready (DoR OK)` | Trabajo listo para ejecutar | DoR completo (`docs/guides/domain-dor-dod.md`) + alcance in/out + riesgos/dependencias | Plan de ejecución en slice chico + criterio de test inicial |
| `In Dev (Red->Green)` | Implementación con TDD-first | Test en rojo (cuando aplique por política) + branch por ticket + responsables confirmados | Evidencia Green + refactor seguro + notas técnicas mínimas |
| `In Test (Integración/E2E + evidencia)` | Validación técnica por riesgo | Build lógico del slice terminado + evidencia de unit/service | Integración/E2E según riesgo + evidencia adjunta en ticket |
| `In Review (PR + compliance)` | Revisión de PR y gates de compliance | PR abierta, checklist de arquitectura/compliance completo, links Jira/SDD | Aprobaciones requeridas + checks en verde + feedback resuelto |
| `Blocked` | Visibilizar impedimento real | Bloqueo explícito | `blocker owner` + `ETA` obligatorios en comentario, y plan de desbloqueo |
| `Done` | Cierre operativo del ticket | Salida válida de `In Review` y evidencia final en ticket | Documentación/links finales + aprendizaje breve (si aplica) |

### Regla de salida de `Blocked`

- Al desbloquear, la tarjeta vuelve a su estado operativo previo (`Ready`, `In Dev`, `In Test` o `In Review`), **no** salta directo a `Done`.

## 4) WIP limits sugeridos

> Ajustar por capacidad real del equipo, pero no superar estos topes sin acuerdo explícito en daily.

| Columna | WIP sugerido |
| --- | --- |
| `Backlog Sprint` | Sin límite (ordenado por prioridad) |
| `Ready (DoR OK)` | `<= 2 x` cantidad de devs activos |
| `In Dev (Red->Green)` | `<= 1` por dev activo |
| `In Test (Integración/E2E + evidencia)` | `<= 2` en paralelo |
| `In Review (PR + compliance)` | `<= 3` en paralelo |
| `Blocked` | `<= 2`; si supera, escalar en el día |
| `lane:expedite` | **WIP global = 1** |

## 5) Política de due dates

## Cuándo se asignan

- `lane:standard`: al entrar a `Ready (DoR OK)`.
- `lane:ops-control`: al entrar a `Ready (DoR OK)` o `In Dev` (lo que ocurra primero).
- `lane:expedite`: al crear el ticket (deadline dentro de 24h).

## Responsables

- **Assignee** propone due date.
- **Tech Lead/owner de dominio** valida coherencia con capacidad y dependencias.
- **Quien facilita la daily** monitorea vencimientos y aging.

## Alertas mínimas

- Alerta preventiva: `T-48h`.
- Alerta crítica: `T-24h`.
- Vencido: escalar en daily y definir plan explícito (replan o expedite).

## 6) Manejo de bloqueos (obligatorio)

Cuando una tarjeta pasa a `Blocked`, el comentario debe incluir:

1. Motivo concreto del bloqueo.
2. `blocker owner` (persona responsable de destrabar).
3. `ETA` de desbloqueo.
4. Próximo checkpoint (fecha/hora).

Plantilla copy/paste:

```md
Bloqueo: <motivo>
Blocker owner: <nombre>
ETA desbloqueo: <YYYY-MM-DD HH:mm TZ>
Siguiente checkpoint: <YYYY-MM-DD HH:mm TZ>
Plan si no se destraba: <acción>
```

## 7) Checklist de daily (rápido)

- [ ] ¿Hay tarjetas en `Blocked` sin owner o sin ETA? Corregir en el acto.
- [ ] ¿`lane:expedite` respeta WIP=1 y SLA <=24h?
- [ ] ¿`Ready` tiene solo trabajo realmente ejecutable (DoR OK)?
- [ ] ¿`In Dev` tiene evidencia Red->Green en progreso?
- [ ] ¿`In Test` acumula tickets sin evidencia de integración/E2E?
- [ ] ¿`In Review` tiene PR/checklists al día?
- [ ] ¿Hay due dates en riesgo (`T-48h` / `T-24h`)?

## 8) Checklist de cierre de sprint

- [ ] Todo `Done` tiene evidencia mínima y links de PR/Jira consistentes.
- [ ] No quedan tickets “fantasma” en `In Test` o `In Review` sin owner claro.
- [ ] Bloqueos cerrados o renegociados con fecha concreta.
- [ ] `lane:expedite` revisada con post-mortem corto (causa + prevención).
- [ ] Lecciones del sprint capturadas en docs/decision-log cuando aplique.

## 9) Reglas para agentes IA en Jira (qué sí / qué no)

## Sí

- Actualizar estado **solo** cuando hay evidencia del gate de salida.
- Mantener labels de lane (`lane:*`) correctas desde el inicio.
- Exigir owner + ETA al mover a `Blocked`.
- Adjuntar evidencia técnica objetiva (tests, PR, checklist compliance).
- Señalar riesgos de WIP/due date antes de que rompan SLA.

## No

- No crear columnas nuevas ni usar columnas para clasificar “tipos de tarea”.
- No mover a `Done` sin evidencia de `In Review`.
- No usar `lane:expedite` para “ganar prioridad” sin urgencia real.
- No dejar tickets bloqueados sin comentario estructurado.
- No modificar alcance del ticket sin dejar trazabilidad en comentario.

## 10) JQLs operativas (Auth-Access)

> Ajustar `project` si corresponde y mantener label de dominio consistente (`domain:auth-access`).

### Vista sprint Auth-Access

```jql
project = KAN
AND labels = "domain:auth-access"
AND sprint in openSprints()
ORDER BY Rank ASC
```

### Bloqueados sin due date (riesgo alto)

```jql
project = KAN
AND labels = "domain:auth-access"
AND status = "Blocked"
AND duedate is EMPTY
ORDER BY updated DESC
```

### Expedite fuera de SLA (>=24h abierto)

```jql
project = KAN
AND labels in ("domain:auth-access", "lane:expedite")
AND status != "Done"
AND created <= -24h
ORDER BY created ASC
```

### Aging en In Test

```jql
project = KAN
AND labels = "domain:auth-access"
AND status = "In Test (Integración/E2E + evidencia)"
AND status changed to "In Test (Integración/E2E + evidencia)" before -2d
ORDER BY updated ASC
```

### In Review con due date vencido

```jql
project = KAN
AND labels = "domain:auth-access"
AND status = "In Review (PR + compliance)"
AND duedate < now()
ORDER BY duedate ASC
```

## References

- `docs/guides/domain-dor-dod.md`
- `docs/guides/pr-merge-governance.md`
- `docs/getting-started/ai-team-workflow.md`
- `docs/domains/auth-access/backlog-mapping.md`
