# Receta — flujo de impresión de punta a punta

Estado: **F1 y F2 implementadas** (2026-11-05) en `SISEM-15-07-2026`, commits
locales **sin push** hasta el visto bueno, igual que
[receta-diseno-stc.md](receta-diseno-stc.md). F3 implementada (P3).

## 1. Objetivo y alcance

Que la simulación cita → check-in → somatometría → consulta → (autorización)
→ receta impresa funcione sin atajos, cerrando solo los huecos encontrados en
la revisión del 2026-11-05. Reglas:

- **Solo lo que falta para el flujo.** Sin pantallas nuevas, sin migraciones,
  sin endpoints nuevos.
- **No cambian** las reglas de imprimibilidad (las decide el builder de la
  receta: consulta cerrada, nota no cancelada, sin autorización pendiente o
  rechazada, con medicamentos activos), ni el permiso
  `documentos.receta.imprimir`, ni la bitácora.
- La UI solo **muestra u oculta** el botón; la regla la sigue aplicando el
  backend (409 si no se puede).

## 2. Revisión del flujo (2026-11-05)

| Paso | Pantalla | Estado |
|---|---|---|
| Agendar cita / check-in | `/recepcion/agendar-cita`, `/recepcion/checkin` | ✅ completo; crea la visita `en_espera` |
| Somatometría | `/clinico/somatometria` | ✅ completo; exige signos completos para `lista_para_doctor` |
| Consulta | `/clinico/consultas/doctor/:visitId` | ✅ captura indicaciones libres ("Guardar receta") y medicamentos del catálogo (`PrescriptionItemsButton`); cerrar no exige receta |
| Autorización | `/clinico/autorizacion-recetas` | ✅ controlado o cuadro especial crea una autorización `pendiente` que bloquea la impresión hasta decidirla |
| Imprimir | `/clinico/expedientes/:folio` → Historial | ❌ **H1**: el botón depende del campo equivocado |
| Imprimir desde la consulta | — | ⚠️ **H2**: el médico no tiene el botón al cerrar |
| Reimprimir | `/farmacia/recetas` | ✅ |
| Lectura de `items` (json) | — | ✅ descartado: la migración `0054_json_columns_to_jsonb` ya lo dejó en `jsonb` |
| Entorno local sin Docker | — | ⚠️ falta Pango (MSYS2) para WeasyPrint; no es código |

### H1 — el botón "Imprimir receta" mira las indicaciones libres

`patient_history_usecase._consultation_to_history_item` arma
`prescriptionItems` con `VisitPrescription.items` (indicaciones de texto
libre). `ExpedienteHistorialTab` muestra el botón solo si ese arreglo no está
vacío. Pero el builder imprime los **medicamentos del catálogo**
(`VisitPrescriptionItem` activos) y da 409 si no hay ninguno. Resultado:

| Caso | Botón hoy | ¿Se puede imprimir? |
|---|---|---|
| Medicamentos sin indicaciones libres | **oculto** | sí → el usuario no puede |
| Indicaciones libres sin medicamentos | visible | no → 409 al tocarlo |
| Ambos | visible | sí |

### H2 — sin impresión al cerrar la consulta

Al cerrar, `DoctorConsultationPage` navega a la cola y el médico tiene que ir
al expediente para imprimir. No bloquea el flujo; es un rodeo.

## 3. Cambios

### F1 (obligatoria) — el historial informa los medicamentos

Backend, `apps/consulta_medica/uses_case/patient_history_usecase.py`:

- Nuevo campo `prescriptionMedications: string[]` en cada consulta: nombre
  de catálogo (con concentración) de los `VisitPrescriptionItem` **activos**
  de la receta activa, mismo filtro que el builder. Se mantiene
  `prescriptionItems` (lo usan la vista y la cancelación de nota).
- Sin N+1 nuevo: `PrescriptionItemRepository.active_names_by_visit` trae los
  medicamentos de todas las visitas del historial en una sola consulta.

Frontend:

- `api/types` del historial: agrega `prescriptionMedications`.
- `ExpedienteHistorialTab`: el botón aparece con `visitStatus === "cerrada"`
  **y** `prescriptionMedications.length > 0`. La línea "Receta:" lista
  medicamentos y, aparte, las indicaciones.

### F2 (recomendada) — imprimir al cerrar la consulta

`DoctorConsultationPage`: mientras la visita está `en_consulta` y el usuario
tiene la capability `documentos.receta.imprimir`, consulta los medicamentos
(`usePrescriptionItems`, ya existe y se invalida al agregar o cancelar). Si hay
activos, el toast "Consulta cerrada" ofrece la
acción **"Imprimir receta"** con `usePrintDocument("receta")`. El clic del
toast abre la pestaña de forma síncrona (requisito del bloqueador de popups).
Si hay autorización pendiente, el backend responde 409 y el hook muestra
"Este documento todavía no se puede imprimir".

### F3 — quitar lo que ya no hace falta

`apps/consulta_medica/impresion/receta.py`: `_general_indications` lee
`items` con `Cast(... TextField)` + `json.loads` y la receta se carga con
`.defer("items")`. Era un rodeo para columnas `json`; con `0054` ya son
`jsonb` en todas las bases. Se reemplaza por `prescription.items` con la misma
limpieza (lista de textos no vacíos). Quedan fuera `json`, `Cast` y
`TextField`.

Nada más se quita: las rutas duplicadas `agendar-cita`/`checkin` usan la misma
página a propósito y no son parte de este cambio.

## 4. Plan de entrega (TDD: Red → Green → Refactor)

| Fase | Tests primero | Código |
|---|---|---|
| F1 back | historial: consulta con medicamentos y sin indicaciones → `prescriptionMedications` con el nombre; ítem cancelado no aparece; consulta sin receta → `[]`; número de queries acotado (`assertNumQueries`) | `patient_history_usecase` |
| F1 front | `ExpedienteHistorialTab`: botón visible con medicamentos y sin indicaciones; oculto con solo indicaciones; oculto si no está cerrada | tipo + componente |
| F2 | página del médico: tras cerrar con medicamentos, el toast trae "Imprimir receta"; sin medicamentos no | `DoctorConsultationPage` |
| F3 | `test_print_receta_nota` sigue verde (ya cubre indicaciones generales y la hoja de controlado) | `receta.py` |

Un commit por fase, solo con sus rutas (`git commit -- <rutas>`).

Las capabilities de impresión pasan de `PrintButton.tsx` a
`shared/components/print/printCapabilities.ts` para que la página del médico
use el mismo requisito que el botón.

Validación: backend en Docker (`docker exec sisem-backend python manage.py
test apps.consulta_medica apps.impresion`); frontend con
`pnpm test` de los archivos tocados.

## 5. Prueba manual (simulación)

1. Check-in de un paciente sin cita (`walk_in`).
2. Somatometría completa → lista para el médico.
3. Consulta: diagnóstico, nota y **solo medicamentos del catálogo**, sin
   indicaciones libres (el caso de H1). Cerrar.
4. F2: el toast ofrece "Imprimir receta" → PDF con ORIGINAL y COPIA.
5. Expediente → Historial: el botón aparece (F1).
6. Repetir con un controlado: primero 409 (autorización pendiente); autorizar
   en `/clinico/autorizacion-recetas`; imprimir → 3 hojas.
7. Reimprimir → "Impresión 2" y marca de reimpresión.

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Otra pantalla usa `prescriptionItems` como "tiene receta" | Se mantiene el campo; solo cambia la condición del botón |
| Base local sin la migración `0054` (F3 fallaría al leer `items`) | Antes de F3: `python manage.py showmigrations consulta_medica`; el historial y el alta de medicamentos ya dependen de `0054` |
| Cambio sin commitear de otra sesión en `expedientes` (`LegacyConsultationHistorySection`) | F1 no toca esos archivos; commit solo con rutas propias |

## 7. Evidencia (2026-11-05)

| Paso | Resultado |
|---|---|
| F1 back, rojo | 5 tests nuevos: `KeyError: 'prescriptionMedications'` (4) y conteo de queries (1) |
| F1 back, verde | `test_patient_history_prescription` + `test_diagnosis_redaction` + `test_note_cancellation`: 58 OK |
| F1 front, rojo | `ExpedienteHistorialTab.ui.test.tsx`: 3 de 4 nuevos fallan; los 6 existentes pasan |
| F2 front | tests escritos antes del código; **no se corrieron en rojo** (la instalación del frontend estaba en curso). Verde junto con F1 |
| Verde front | 5 archivos, 45 tests (historial, página del médico, `PrintButton`, `usePrintDocument`, `FichaModal`); `tsc --noEmit` sin errores |
| Línea base back (7 apps del flujo) | 1316 tests: 8 errores en `setUpClass` de `*MigrationTests` (`UNIQUE constraint failed: django_content_type`), dependen del orden de ejecución: la clase sola pasa. Ajenos a este cambio |

Frontend corrido en un contenedor `node:22.18-alpine` con el volumen de
`node_modules`: el contenedor `sisem-frontend` no arranca (su imagen no trae
`pnpm`).

### Prueba de punta a punta (`test_flujo_cita_a_receta.py`)

Por la API, con login real (cookie JWT + CSRF) y un usuario por rol:
recepción registra la llegada (`walk_in`) y la pasa a somatometría →
somatometría captura signos (`lista_para_doctor`) → el médico inicia, guarda
diagnóstico, agrega el medicamento y cierra → historial →
`GET /impresion/receta/<visita>` devuelve un PDF real. Solo se simula el padrón
del paciente (`get_patient_header`, en operación viene del legado).

| Caso | Resultado |
|---|---|
| Medicamento básico, sin indicaciones libres | historial con `prescriptionMedications`, PDF copia 1 y reimpresión copia 2, 2 `PrintLog` |
| Controlado | 409 `DOCUMENT_NOT_PRINTABLE` → el autorizador aprueba → PDF |

Reglas del flujo que aparecieron al recorrerlo (no son bugs, son requisitos
para la simulación manual):

- Todo usuario necesita **centro de atención asignado**; sin él, recepción
  recibe `CENTRO_NO_ASIGNADO` (403).
- El médico tiene que **guardar el diagnóstico antes de agregar
  medicamentos**; si no, `CONSULTATION_NOT_FOUND` (409).
- El cambio de estado de la visita es `PATCH /visits/<id>/status`.

## 8. Pasos para concluir (2026-11-05)

Quién: **C** = Claude (código y verificación), **U** = usuario.

| # | Paso | Quién | Estado |
|---|---|---|---|
| P1 | Entorno de desarrollo Windows: Pango (MSYS2) instalado; `WEASYPRINT_DLL_DIRECTORIES` fija en el usuario | U / C | ✅ Pango 1.58; variable fija en el usuario |
| P2 | `base.css`: `Arial` después de `Liberation Sans` para que el PDF en Windows mida igual que en el servidor | C | ✅ el PDF en Windows usa Arial |
| P3 | F3: quitar el rodeo `Cast`/`json.loads`/`defer` de `receta.py` (base de desarrollo con `0054` aplicada, sin migraciones pendientes) | C | ✅ `items` es `jsonb` en la base de desarrollo y se lee por el ORM |
| P4 | Verificación: tests de impresión, receta, historial y flujo en Docker; render de la receta en Windows | C | ✅ 125 tests OK; PDF en Windows OK |
| P5 | Prueba manual en el navegador (sección 5), con usuarios con centro asignado y permiso `clinico:recetas:imprimir` | U | pendiente |
| P6 | Descartar `backend/requirements.txt` del `pip freeze` (`git checkout -- backend/requirements.txt`) | U | pendiente |
| P7 | Visto bueno → push de `SISEM-15-07-2026` | U → C | pendiente |
| P8 | Servidor: `docker compose build backend`, `python manage.py migrate` (trae la `0068`, solo agrega columnas) y levantar | U | pendiente |
| P9 | Decisiones abiertas de la receta (D1–D11 de `receta-diseno-stc.md`); no bloquean | áreas | D8 ✅ (§9); D9 espera a farmacia; resto abierto |

## 9. D8: vía, frecuencia y duración (2026-11-05)

Decisión del usuario: columnas nuevas, **obligatorias para cada medicamento
nuevo**. D9 (grupo del controlado) espera a farmacia y jurídico.

| Capa | Cambio |
|---|---|
| Modelo | `VisitPrescriptionItem.route` (`via`, choices `Route`: oral, sublingual, tópica, oftálmica, ótica, nasal, inhalada, rectal, vaginal, IM, IV, subcutánea, transdérmica), `frequency` (`frecuencia`, 60), `duration` (`duracion`, 60). Nulas |
| Migración | `0068_receta_via_frecuencia_duracion`: 3 `AddField` nulos; no toca datos |
| Aplicación | `add_prescription_item` → `_validate_administration`: 422 `VALIDATION_ERROR` con `details` por campo si falta alguno o la vía no existe |
| Presentación | `AddPrescriptionItemSerializer` acepta `route`, `frequency`, `duration` (solo forma); el contrato del renglón agrega `route`, `routeLabel`, `frequency`, `duration` |
| Receta | `_administration_text`: `dosis · vía · frecuencia · duración · indicaciones`; los renglones previos se imprimen como antes |
| Frontend | `PrescriptionItemsButton`: vía (lista), frecuencia y duración obligatorias; el listado las muestra. Lista de vías en `domain/administration-routes.ts` (espejo del backend) |

Evidencia: backend en rojo (`ImportError`) → 943 tests OK en `consulta_medica`,
`farmacia`, `autorizaciones` e `impresion` (41 llamadas y 4 payloads de tests
existentes reciben los campos vía `tests/receta_fixtures.ADMINISTRATION`).
Frontend: 3 de 4 tests nuevos en rojo → 4 OK; `tsc` sin errores; 95 de 96 en
`flujo-clinico`, `farmacia`, `expedientes` y `print` (el que falla,
`LegacyConsultationHistorySection`, pasa corrido solo: tiempo bajo carga, y
tiene cambios sin commitear de otra sesión).

Gap documental: no existe documentación de API de
`/visits/<id>/prescription-items` en `docs/api/`.

**Base de desarrollo:** hay que aplicar la `0068` (`python manage.py migrate`);
sin ella, agregar o listar medicamentos falla porque las columnas no existen.
