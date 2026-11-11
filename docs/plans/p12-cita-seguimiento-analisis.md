# P-12 Cita de seguimiento — análisis antes de implementar

Estado: **análisis, sin código** (2026-11-11, revisión 2). Proceso 1 de la lista
de crónicos (ver [cronicos-control.md](cronicos-control.md)). El plan de
implementación sale de las decisiones de la sección 7.

> TL;DR: contra el legado, P-12 está **completo y no se toca**. Visto como
> proceso de punta a punta le faltan 7 complementos: la cita no se cancela al
> cancelar la nota, el paciente se va sin comprobante, la indicación vencida se
> pierde sin cierre, la auditoría del cierre no registra la cita, la nota
> impresa no dice hora ni folio, no hay indicadores, y crónicos necesita
> agendar controles a 90–180 días. Todos se resuelven **agregando**, sin
> cambiar el comportamiento actual.

## 0. Regla de este análisis: solo agregar

Lo que ya funciona queda igual: mismas pantallas, mismas validaciones, mismos
contratos, mismas ventanas. Los complementos solo pueden:

- agregar columnas que admiten vacío, tablas, estados derivados o endpoints nuevos;
- agregar campos **opcionales** a contratos existentes (nadie que no los lea se entera);
- agregar filtros **opcionales** (sin el filtro, la respuesta es la de hoy).

Si un complemento no cabe en esas tres formas, no entra en este plan.

## 1. Reglas del legado contra SIRES

Fuente del legado: mapa de procesos P-12 (`parte_familiar.jsp` → `horario_fam.jsp`)
y P-06. Fuente de SIRES: `consulta_medica/uses_case/follow_up_usecase.py`,
`recepcion/uses_case/agendar_cita_usecase.py`, `continuar-en-trabajo.md` §7, §9–§16.

| # | Regla del legado | SIRES hoy | Estado |
|---|---|---|---|
| 1 | Casilla "Cita Para" en el SOAP o el complemento | "Indicar fecha de seguimiento" + calendario y horarios en la consulta | ✅ |
| 2 | Mismo motor de agenda que recepción | `agendar_cita`, el mismo caso de uso de recepción | ✅ |
| 3 | Medicina general agenda con el **médico familiar**; otros servicios, con el médico actual | Siempre con el médico que atiende; si el paciente tiene **otro consultorio familiar** (P-03), la cita la agenda recepción | ⚠️ Distinto a propósito (decisión 2026-11-10) |
| 4 | La cita se crea por AJAX **aunque no se guarde la nota** | Se crea **al cerrar la nota, en la misma transacción** | ✅ Mejora |
| 5 | Desmarcar la casilla da de baja la cita | Antes de cerrar no hay cita; después, recepción cancela o reprograma (B5) | ✅ |
| 6 | La fecha queda en la nota (`his_notas.fe_cita`) | `fe_seguimiento`, posterior a la consulta | ✅ |
| 7 | Máximo 3 citas por expediente por día; no dos el mismo día al paciente | Parámetros `citas.max_por_expediente_dia` = 3 y `citas.max_por_paciente_dia` = 1 | ✅ |
| 8 | Sin horario, la cita la agenda recepción | "Seguimientos por agendar" (§16), de hoy−30 a hoy+60 | ✅ |
| 9 | — | Ficha automática, "Por llegar" y no asistió automático (§12–§14) | ✅ Nuevo |

**Conclusión:** contra el legado, P-12 está completo. La marca "sin revisar"
del mapa (2026-10-16) es anterior a estos cambios.

## 2. El proceso de punta a punta (ciclo de vida del seguimiento)

Buenas prácticas de un proceso: cada caso tiene un estado, un responsable, un
cierre explícito y una medida. Hoy el seguimiento **no tiene estado propio**:
se deduce de si existe la fecha en la nota y si hay una cita con la convención
de notas.

| Estado (derivado, no se guarda) | Cómo se sabe hoy | Responsable | ¿Tiene cierre? |
|---|---|---|---|
| Indicado | Nota cerrada con `fe_seguimiento` y sin cita | Recepción | ❌ Si nadie lo agenda, sale de la lista a los 30 días **sin registro** |
| Agendado | Cita no cancelada con motivo "Cita de seguimiento" y notas "Consulta <folio>" | Recepción / médico | ✅ |
| Atendido | La cita pasa a atendida al cerrar la consulta siguiente | Médico | ✅ |
| No asistió | No asistió automático (§14) | Sistema | ✅ Pero nadie lo vuelve a citar |
| Descartado | — | — | ❌ No existe (paciente no quiere, ya se atendió en otro lado, falleció) |
| Huérfano | La nota se cancela y la cita sigue viva | — | ❌ Ver G1 |

## 3. Huecos encontrados (todos se cubren agregando)

| # | Hueco | Evidencia | Riesgo |
|---|---|---|---|
| G1 | **Cancelar la nota no cancela su cita de seguimiento** | `note_cancellation_usecase._gather` cancela recetas, autorizaciones, pases, incapacidades y estudios; no la cita | El paciente llega a una cita de una consulta anulada; ocupa un horario |
| G2 | **El paciente se va sin comprobante** de la cita presencial (la que da el médico o recepción) | El único comprobante es el del portal (`portal_citas/services/pdf_comprobante_service.py`, con QR); el registro de impresión solo tiene ficha, receta y nota. Las citas presenciales **no se notifican por correo** (decisión del usuario 2026-11-11: el paciente está en la unidad) | Olvida fecha u hora; inasistencia evitable |
| G3 | La indicación sin agendar **se pierde sin cierre** | Ventana de hoy−30 de §16 | No hay forma de saber cuántos seguimientos se perdieron |
| G4 | No existe **descartar** un seguimiento con motivo | — | La lista acumula casos que nunca se van a agendar |
| G5 | La auditoría del cierre **no registra la cita** | `_close_consultation_datos_despues` no incluye la cita; solo queda en `citas_estatus_log` (canal MEDICO) | Trazabilidad NOM-024 repartida en dos lugares |
| G6 | La nota impresa dice solo la fecha | `nota.html`: "Cita de seguimiento: {fecha}" | El paciente sale sin hora, consultorio ni folio |
| G7 | **Sin indicadores**: indicados, agendados, atendidos, perdidos | — | No se puede medir el proceso |

### Huecos propios de crónicos

| # | Hueco | Evidencia | Riesgo |
|---|---|---|---|
| C1 | Los horarios se generan **30 días adelante** | `recepcion/tasks.py` `dias_adelante=30` (60 al cambiar consultorio) | Un control a 90–180 días no se agenda desde la consulta |
| C2 | El atajo "3 meses" no encuentra día y no dice por qué | `FOLLOW_UP_SHORTCUTS` + `next_follow_up_day` | El médico cree que es una falla |
| C3 | `fe_seguimiento` (nota) y `fe_proximo_control` (control) no se hablan | Modelos | Dos fechas distintas para lo mismo |
| C4 | La cita no sabe que es un control de crónicos | Motivo genérico | No se mide inasistencia de crónicos ni se prioriza |

## 4. Complementos propuestos (sin cambiar lo existente)

| # | Complemento | Cubre | Cómo se agrega | Qué NO cambia |
|---|---|---|---|---|
| K1 | La cancelación de la nota **también cancela su cita de seguimiento** (si no tiene ficha), con motivo "Consulta cancelada" | G1 | Un paso más en la cascada existente, mismo patrón que pases e incapacidades | Las validaciones, permisos y el resto de la cascada |
| K2 | **Comprobante de cita impreso** para las citas presenciales (médico y recepción): folio, fecha, hora, médico, consultorio y "preséntese N minutos antes". Se ofrece al agendar ("Imprimir comprobante", igual que la receta al cerrar) y se puede reimprimir desde la agenda | G2 | Documento nuevo `cita` en `impresion/registry.py`, mismo motor que ficha, receta y nota. Sin QR: las citas presenciales generan su ficha automática y no hacen check-in | El comprobante y los correos del portal; las citas presenciales siguen **sin correo** |
| K3 | **Cierre de seguimiento**: tabla `cns_seguimiento_cierre` (nota, motivo de catálogo, quién, cuándo) para **descartar** con motivo | G3, G4 | Tabla nueva + botón "Descartar" en "Seguimientos por agendar"; la lista excluye los cerrados | La ventana y los filtros actuales de la lista |
| K4 | Campo opcional `followUp` (folio, fecha y hora) en el `datos_despues` de `ConsultationClosed` | G5 | Un campo más en la foto de auditoría | El evento, su invariante de 1 por request y lo demás del snapshot |
| K5 | Nota impresa con hora, consultorio y folio cuando hay cita | G6 | Línea condicional en `nota.html` | La nota sin cita se imprime igual |
| K6 | Indicadores: indicados, agendados, atendidos, no asistió, descartados y perdidos, por centro y periodo | G7 | Endpoint de solo lectura + reporte | Ninguna tabla operativa |
| K7 | **Control de crónicos con fecha larga**: si no hay horarios a esa fecha, el atajo explica "Sin horarios generados aún; queda como fecha indicada y la agenda recepción" | C1, C2 | Mensaje nuevo; el comportamiento de "fecha indicada" ya existe | La generación de horarios (30 días) y el calendario |
| K8 | El control de crónicos **propone** la fecha de seguimiento de la nota **solo si está vacía** | C3 | Rellena el campo; el médico la cambia si quiere | La validación de `fe_seguimiento` y las notas con fecha ya puesta |
| K9 | Liga real control ↔ cita: `id_cita` (admite vacío) en `cns_control_cronico` | C4 | Columna nueva; se llena cuando la cita se agenda desde la consulta o desde la lista | El motivo y las notas de la cita (la convención actual sigue) |
| K10 | Filtro **opcional** "Solo controles de crónicos" y rango hasta +180 días **solo con ese filtro** en "Seguimientos por agendar" | C1, C4 | Parámetro opcional del endpoint | Sin el filtro, la lista es la de hoy (hoy−30 a hoy+60) |
| K11 | **Aviso en recepción** al buscar al paciente: "Tiene un seguimiento indicado para el {fecha} sin agendar" (y "control de crónicos vencido") | P1 | Endpoint nuevo de solo lectura (o campo opcional en `patient-lookup`) con el contrato `seguimientos_indicados` que ya existe | La búsqueda de paciente y su respuesta actual |
| K12 | **Horizonte de horarios como parámetro** `citas.dias_generacion_horarios` (por omisión **30**, el valor de hoy) | P2, C1 | `get_param` en la tarea diaria, igual que los topes de citas | Con el valor por omisión, la generación es idéntica a hoy; subirlo lo decide la institución |

### 4.1 Lo que cambia por ser presencial (decisión del usuario 2026-11-11)

Las citas de recepción y del médico se sacan **en persona**: no hay correo ni
llamada. Entonces el único momento para dar la cita es **mientras el paciente
está en la unidad**.

| # | Consecuencia | Complemento |
|---|---|---|
| P1 | Si el seguimiento no se agenda ese día, la próxima oportunidad es **cuando el paciente vuelva por otro motivo**. Hoy recepción no se entera al buscarlo | K11 |
| P2 | La opción "fecha indicada, recepción agenda después" **no sirve para controles largos**: recepción no tiene cómo localizar al paciente en 60 días | K12: con horarios a ~100–190 días el control de 90–180 días se agenda **en la misma visita** |

Por eso, para crónicos, la recomendación cambia de "fecha indicada" a
**subir el horizonte con K12** (lo decide la institución: más filas de
horarios y más reprogramaciones por ausencias lejanas). Con 30 días, K11 es
la red de seguridad.

## 5. Responsables (quién hace qué)

| Paso | Médico | Recepción | Sistema |
|---|---|---|---|
| Indicar fecha / elegir horario | Hace | — | Valida reglas de agenda |
| Agendar lo indicado | — | Hace (lista §16) | — |
| Entregar comprobante al paciente | Imprime al cerrar (K2) | Imprime al agendar (K2) | — |
| Descartar con motivo | Puede | Hace (K3) | — |
| Cancelar al anular la nota | — | — | K1 |
| No asistió | — | Revisa y vuelve a citar | Marca (§14) |
| Medir | Jefatura | — | K6 |

## 6. Datos

| Legado | SIRES | Nota |
|---|---|---|
| `det_agendafam` (con `cd_snota`) | `citas_medicas` (motivo + notas "Consulta <folio>") | Liga cita ↔ nota por convención de texto; se conserva |
| `his_notas.fe_cita` | `cns_visit_consultation.fe_seguimiento` | — |
| — | `cns_control_cronico.fe_proximo_control` | Se liga con K8 y K9 |
| `det_agendafam` histórico | Sin migrar | D5 |

## 7. Decisiones pendientes

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| D1 | Orden de los complementos | Por riesgo o por crónicos | **Por riesgo**: K1 → K4 → K5 → K3 → K2 → K8 → K9 → K10 → K7 → K6 |
| D2 | Motivos de descarte (K3) | Catálogo nuevo o reutilizar `cat_motivos` de cancelación de cita | **Catálogo nuevo** chico: "No desea", "Atendido en otra unidad", "Defunción", "Baja del servicio", "Otro" (con detalle) |
| D3 | Comprobante de la cita presencial (K2) | Comprobante propio / solo la nota impresa (K5) | **Comprobante propio**: la nota impresa es expediente, no siempre se entrega al paciente, y recepción también agenda sin nota. Decidido: **sin correo** para citas presenciales |
| D4 | K1 con la cita que ya tiene ficha | Cancelarla también / dejarla y avisar | **Dejarla y avisar** en la bitácora: si ya tiene ficha, el paciente ya está en la unidad |
| D5 | Migrar `det_agendafam` histórico | Migrar / dejar en el respaldo | **Respaldo**: citas pasadas sin valor operativo; confirmar contra la política de retención |

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| K1 cancela una cita que el paciente necesitaba igual | Solo citas sin ficha (D4) y motivo visible en la bitácora; recepción puede volver a agendar |
| K2 el comprobante muestra datos personales si se queda en el mostrador | Solo nombre y expediente, sin diagnóstico ni motivo clínico de la cita |
| K3 se usa para "limpiar" la lista sin atender | Motivo obligatorio + auditoría + indicador de descartados (K6) |

## 9. Criterio de terminado (por complemento, cuando se aprueben)

- [ ] Pruebas primero de cada complemento, incluida una que demuestre que **lo existente no cambió** (mismo contrato y misma respuesta sin los campos o filtros nuevos).
- [ ] K1: cancelar una nota con cita sin ficha la cancela con motivo; con ficha, no y queda la nota en la bitácora.
- [ ] K4: `ConsultationClosed` trae `followUp` solo cuando hubo cita.
- [ ] K3: descartar pide motivo, queda auditado y el caso sale de la lista.
- [ ] Documentación: este archivo, `continuar-en-trabajo.md` y la marca de P-12 en el mapa.
