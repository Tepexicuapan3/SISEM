# P-12 Cita de seguimiento — análisis antes de implementar

Estado: **análisis, sin código** (2026-11-11). Proceso 1 de la lista de crónicos
(ver [cronicos-control.md](cronicos-control.md)). El siguiente plan de
implementación sale de las decisiones de la sección 5.

> TL;DR: P-12 ya funciona para seguimientos de **hasta 30 días**. Para crónicos
> (control cada 90 o 180 días) no alcanza: el médico no tiene horarios generados
> tan lejos, el atajo "3 meses" no encuentra día, y la fecha del próximo control
> del programa y la fecha de seguimiento de la nota son dos datos que no se
> hablan. Faltan 4 decisiones antes de tocar código.

## 1. Reglas del legado contra SIRES

Fuente del legado: mapa de procesos P-12 (`parte_familiar.jsp` → `horario_fam.jsp`)
y P-06 (agenda). Fuente de SIRES: `consulta_medica/uses_case/follow_up_usecase.py`,
`recepcion/uses_case/agendar_cita_usecase.py`, `continuar-en-trabajo.md` §7, §9–§16.

| # | Regla del legado | SIRES hoy | Estado |
|---|---|---|---|
| 1 | Casilla "Cita Para" en el SOAP o el complemento | "Indicar fecha de seguimiento" + calendario y horarios en la consulta | ✅ |
| 2 | Mismo motor de agenda que recepción | `agendar_cita`, el mismo caso de uso de recepción | ✅ |
| 3 | Medicina general (servicios 1 y 6) agenda con el **médico familiar**; otros servicios, con el médico actual | Siempre con el médico que atiende. Si el paciente tiene **otro consultorio familiar** (P-03), la nota no se cierra con ese horario y la cita la agenda recepción | ⚠️ Distinto a propósito (decisión 2026-11-10) |
| 4 | La cita se crea por AJAX **aunque no se guarde la nota** (dos escrituras separadas) | Se crea **al cerrar la nota, en la misma transacción**; si falla, la nota no se cierra | ✅ Mejora |
| 5 | Desmarcar la casilla da de baja la cita (`det_agendafam = B`) | Antes de cerrar no hay cita que dar de baja; después, recepción cancela o reprograma (B5) | ✅ |
| 6 | La fecha queda en la nota (`his_notas.fe_cita`) | `fe_seguimiento` en la consulta, posterior a la consulta | ✅ |
| 7 | Máximo 3 citas por expediente por día; no dos el mismo día al mismo paciente (P-06) | `citas.max_por_expediente_dia` = 3 y `citas.max_por_paciente_dia` = 1 (parámetros) | ✅ |
| 8 | Sin horario elegido, la cita la agenda recepción | "Seguimientos por agendar" en Próximas citas (§16), de hoy−30 a hoy+60 | ✅ |
| 9 | — (no existía) | Ficha automática el día de la cita, "Por llegar" y no asistió automático (§12–§14) | ✅ Nuevo |

**Conclusión:** contra el legado, P-12 está **completo**. La marca "sin revisar"
del mapa (2026-10-16) es anterior a estos cambios.

## 2. Datos

| Legado | SIRES | Nota |
|---|---|---|
| `det_agendafam` (con `cd_snota`) | `citas_medicas` (motivo "Cita de seguimiento", notas "Consulta <folio>") | La liga cita ↔ nota es por **convención de texto**, no por llave foránea |
| `his_notas.fe_cita` | `cns_visit_consultation.fe_seguimiento` | — |
| — | `cns_control_cronico.fe_proximo_control` | Nuevo (crónicos, entrega 2). **No está ligado** a `fe_seguimiento` ni a la cita |
| `det_agendafam` histórico | Sin migrar | Volumen por medir en `Dump20260903.sql`; ver decisión D4 |

## 3. Hallazgos contra crónicos

| # | Hallazgo | Evidencia | Impacto |
|---|---|---|---|
| H1 | Los horarios de los médicos se generan **30 días adelante** (tarea diaria; 60 al cambiar el consultorio) | `recepcion/tasks.py` `dias_adelante=30`; `consultorio_usecase.py` `dias_adelante=60` | Un control a 90 o 180 días **no se puede agendar** desde la consulta |
| H2 | El atajo "3 meses" busca el primer día libre desde hoy+3 meses; no hay horarios ahí | `FOLLOW_UP_SHORTCUTS` + `next_follow_up_day` | El atajo responde "sin lugar" y el médico no entiende por qué |
| H3 | El calendario pide rangos de hasta 62 días | `FOLLOW_UP_DAYS_MAX_RANGE = 62` | Solo afecta si se generan horarios más lejos (D1) |
| H4 | "Seguimientos por agendar" muestra de hoy−30 a hoy+60 | §16 | Un seguimiento a 90 días aparece en la lista recién 30 días antes; puede ser suficiente (D2) |
| H5 | Dos fechas para lo mismo: `fe_seguimiento` (nota) y `fe_proximo_control` (control de crónicos) | Modelos | Pueden quedar distintas: el médico propone 90 días en el control y pone 30 en la nota |
| H6 | La cita no sabe que es un control de crónicos | Motivo genérico "Cita de seguimiento" | Recepción no puede priorizarlos ni el tablero puede medir inasistencia de crónicos |
| H7 | El no asistió automático ya existe (§14) | `marcar_fichas_no_llegaron` | Sirve para medir **inasistencia de crónicos** sin trabajo extra, si se liga la cita al control (D3) |

## 4. Alternativas para el horizonte (H1–H4)

| Opción | Qué es | A favor | En contra |
|---|---|---|---|
| **A. Fecha indicada + recepción agenda cuando hay horarios** (recomendada) | Para controles de más de 30 días el médico deja **solo la fecha**; aparece en "Seguimientos por agendar" y recepción la agenda cuando ya hay horarios | No cambia la generación de horarios ni la carga de la base; reutiliza lo que ya existe (§16) | La cita no queda reservada el día de la consulta; depende de que recepción revise la lista |
| B. Generar horarios a 180 días | La tarea diaria crea horarios a 6 meses | El médico reserva el control en el momento | 6 veces más filas en `citas_horarios_disponibles`; las ausencias y los cambios de horario lejanos obligan a reprogramar más citas |
| C. Cita "tentativa" sin horario | Cita con fecha y sin hora que recepción confirma después | El paciente sale con una fecha | Estado nuevo en las citas, el portal y el check-in: es mucho para el beneficio |

## 5. Decisiones pendientes (las toma el usuario o la institución)

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| D1 | Horizonte de los controles largos | A, B o C (sección 4) | **A** |
| D2 | Ventana de "Seguimientos por agendar" | Dejar hoy+60 o ampliar a hoy+180 | Ampliar a **+180 solo para controles de crónicos** (filtro aparte), para que recepción los vea con tiempo |
| D3 | Ligar la cita y el control | (a) Sin liga; (b) el control lleva `id_cita` y la cita un motivo "Control de crónicos"; (c) liga por la convención de notas | **(b)**: llave real, no texto. Permite medir inasistencia (H7) |
| D4 | Una sola fecha (H5) | (a) El control propone y llena `fe_seguimiento`; (b) dos fechas independientes | **(a)**: el control **sugiere** la fecha de seguimiento de la nota y el médico la puede cambiar; se guarda la que quede |
| D5 | Migrar `det_agendafam` histórico | Migrar, o dejarlo en el respaldo del legado | Dejarlo en el respaldo: son citas pasadas sin valor operativo. Confirmar contra la política de retención (no es expediente) |

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Recepción no revisa "Seguimientos por agendar" y el control se pierde | Contador en el menú de recepción y "vencido" en rojo (ya existe `vencido`); el tablero de crónicos muestra los controles sin cita |
| El médico cree que el control quedó agendado cuando solo quedó la fecha | Mensaje explícito al cerrar: "Fecha indicada, la cita la agenda recepción" |
| Doble fuente de fecha (si se elige D4-b) | Elegir D4-a |

## 7. Criterio de terminado del plan de implementación (cuando se aprueben las decisiones)

- [ ] Pruebas primero: control de 90 días sin horarios → queda como fecha indicada y aparece en la lista de recepción.
- [ ] El control sugiere `fe_seguimiento` y la nota guarda la fecha final (D4).
- [ ] La cita agendada desde la lista queda ligada al control (D3) y su no asistió se ve en el panel de crónicos.
- [ ] El atajo "3 meses" explica por qué no hay horarios en lugar de solo "sin lugar".
- [ ] Documentación actualizada: este archivo, `continuar-en-trabajo.md` y la marca de P-12 en el mapa.
