# Plan: contraer la llave vieja (`no_exp` + `pk_num` → `id_paciente`)

> Estado: **plan, sin empezar** (2026-10-27). Continúa el plan
> [identidad-paciente.md](identidad-paciente.md): expandir (hecho) → migrar (a medias) → **contraer**.

## Objetivo

Que dentro de SIRES cada fila de atención identifique al paciente **solo por `id_paciente`**
(la afiliación atendida) y que la historia se lea **por `id_persona`**. La llave vieja deja de
copiarse en cada tabla: vive una sola vez, en `cns_paciente` y `cns_identificador_paciente`.

## Decisiones (usuario, 2026-10-27)

| # | Decisión | Consecuencia |
|---|---|---|
| 1 | Todo paciente tiene expediente, propio o del titular | `noExp` obligatorio en fichas y citas; `id_paciente` NOT NULL en todas las tablas que migran |
| 2 | Las búsquedas por expediente se quedan tal cual; `id_paciente` es interno y no se le da a nadie | **La API sigue hablando en `noExp` + `pkNum`.** El backend traduce una vez, en la entrada, y de ahí para adentro usa `id_paciente`. El frontend casi no cambia |
| 3 | Las columnas viejas se congelan y después se borran | Una versión con `no_exp`/`pk_num` sin uso (solo respaldo de lectura); en la siguiente, se borran |

## Enfoque: traducir en la frontera

```
Pantalla / API  ──noExp + pkNum──▶  vista (frontera)  ──id_paciente──▶  caso de uso → repositorio → tabla
                                     paciente_de_llave()                 (sin no_exp / pk_num)
Respuesta       ◀──noExp + pkNum──  se arma desde cns_paciente (JOIN), no desde la tabla de atención
```

- `paciente_de_llave(no_exp, pk_num)`: una función para todas las vistas. Usa la puerta central
  (normaliza el expediente, resuelve el provisional por `cd_provisional`, crea el registro si
  corresponde) y devuelve el `Patient`. Una sola consulta por índice único.
- Las lecturas de historia van por persona en un solo JOIN (`patient__person_id = X`), sin el
  respaldo por llave vieja.
- El provisional sigue viajando con su `cd_provisional` en `pkNum` en la API: el rango
  > 100 000 000 se mantiene (ver "Fuera de alcance").

## Qué se queda con `no_exp` / `pk_num` (es identidad o es una puerta de entrada)

| Dónde | Por qué |
|---|---|
| `cns_paciente`, `cns_identificador_paciente` | Son la identidad: ahí vive la llave, una sola vez |
| `cns_paciente_provisional`, `cns_paciente_sermed`, `cns_persona_descarte` | Hablan del titular o de un candidato de SERMED |
| Réplica de Expedientes (`administracion/models/empleado.py`, `familiar.py`), sincronización con SERMED, búsqueda de expedientes | Sistema externo (decisión 2) |
| Legado: importadores, `legacy_family_map`, `family_key_fix_service`, `legado_*` | Hablan con la llave del legado |
| Portal de citas (`portal_miembros`), solicitudes ARCO, padrones | Puertas de entrada por expediente (decisión 2) |
| Bitácoras de acceso y auditoría | Evidencia de lo que se consultó: se registra como se pidió |
| API y frontend | Decisión 2: el usuario trabaja con expediente |

## Qué migra a `id_paciente` (inventario del 2026-10-27)

Usos de `no_exp`/`pk_num` en código de producción (sin tests ni migraciones):

| Bloque | Módulo | Tablas | Archivos principales (usos) |
|---|---|---|---|
| **C0** | Frontera | — | función `paciente_de_llave`; `noExp` obligatorio en `recepcion/serializers.py` y `recepcion/views/citas_views.py` |
| **C1** | Recepción | `rcp_visits`, `citas_medicas` | `repositories/citas_repository.py` (28), `repositories/visit_repository.py` (28), `uses_case/visit_queue_usecase.py` (23), `uses_case/qr_checkin_usecase.py` (22), `services/vigencia_service.py` (21), `views/citas_views.py` (19), `services/ficha_service.py` (12), `views/__init__.py` (11), `services/clinica_paciente_service.py` (8), `impresion/ficha.py` (6) |
| **C2** | Somatometría | `smt_visit_vitals`, `smt_patient_latest_vitals` | `repositories/vitals_repository.py` (29), `uses_case/capture_vitals_usecase.py` (10) |
| **C3** | Consulta médica | `cns_allergy`, `cns_medical_leave`, `cns_study_result`, `cns_stomatology_history`, `cns_odontograma`, `cns_clinical_history`, antecedentes, hábitos, tratamiento dental (`PatientRecordBase`) | `views.py` (220), `views_unified_history.py` (99), `uses_case/patient_record_usecase.py` (63), `services/patient_link_service.py` (61), `repositories/clinical_history_repository.py` (42), `repositories/allergy_repository.py` (24), `repositories/medical_leave_repository.py` (22), `repositories/odontogram_repository.py` (22) y el resto de `uses_case/` y `repositories/` (≈15 archivos, < 20 usos cada uno) |
| **C4** | Otros módulos | `cir_surgery`, `hsp_admission`, `amb_request`, `ref_referral`, `contratos_oxigeno` | `pases/repositories/referral_repository.py` (24), `contratos_oxigeno/derechohabiente_service.py` (14), `cirugias/repositories/surgery_repository.py` (12), `ambulancias/repositories/ambulance_request_repository.py` (12) y sus vistas/casos de uso |
| **C5** | Impresión y reportes | — | `impresion/services/patient_header.py` (35), `impresion/uses_case/print_document_usecase.py` (8), `consulta_medica/impresion/*`, `*/services/report_export_service.py`: el expediente se toma de `cns_paciente` por JOIN |
| **C6** | **Congelar** | las de C1–C4 | `id_paciente` NOT NULL; el código deja de escribir `no_exp`/`pk_num` (columnas a NULL permitido, sin uso); se retira la doble escritura (`operational_link_service`, `patient_link_service._link_on_save`) y el respaldo por llave vieja de `for_patient` |
| **C7** | **Borrar** (versión siguiente) | las de C1–C4 | Migración que elimina `no_exp`/`pk_num` de esas tablas, con respaldo previo |

Tamaño de referencia: unos 100 archivos de backend tocan la llave; de ellos, los de la tabla de
"se queda" no cambian. El frontend no cambia, salvo donde lea `noExp`/`pkNum` de una respuesta que
deje de traerlos (se mantienen en las respuestas, armados desde `cns_paciente`).

## Cómo se trabaja cada bloque

1. La vista resuelve el paciente con `paciente_de_llave` y pasa `patient` al caso de uso.
2. Repositorios y casos de uso filtran y crean por `patient` (o por persona, en lecturas de historia).
3. Las respuestas toman `noExp`/`pkNum` de `cns_paciente` (`select_related("patient")`).
4. Tests del módulo; al cerrar el bloque, suite de las apps afectadas, commit, push y despliegue.

Durante C1–C5 las columnas viejas se siguen llenando (doble escritura): si algo falla, se vuelve
atrás sin perder datos. Recién C6 deja de escribirlas.

## Verificación antes de C6 (en el servidor, solo lectura)

```sql
-- Tiene que dar 0 en cada tabla de C1–C4.
SELECT count(*) FROM rcp_visits WHERE id_paciente IS NULL;
-- ... (mismo SELECT del 2026-10-27, que dio 0 en las 14 tablas)
```

## Fuera de alcance

- **Achicar el rango del provisional:** la API sigue usando `pkNum` y el `cd_provisional` viaja ahí;
  con números chicos chocaría con un `PK_NUM` real. Se revisa solo si algún día la API deja de
  usar la llave.
- Legado, portal, ARCO, padrones y bitácoras (decisión 2).
