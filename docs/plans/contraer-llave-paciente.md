# Plan: contraer la llave vieja (`no_exp` + `pk_num` → `id_paciente`)

> Estado: **C0 a C6 hechos** (2026-10-27); C7 (borrar columnas) en la versión siguiente. Continúa el plan
> [identidad-paciente.md](identidad-paciente.md): expandir (hecho) → migrar (a medias) → **contraer**.

## Objetivo

Que dentro de SIRES cada fila de atención identifique al paciente **solo por `id_paciente`**
(la afiliación atendida) y que la historia se lea **por `id_persona`**. La llave vieja deja de
copiarse en cada tabla: vive una sola vez, en `cns_paciente` y `cns_identificador_paciente`.

## Decisiones (usuario, 2026-10-27)

| # | Decisión | Consecuencia |
|---|---|---|
| 1 | Todo paciente tiene expediente, propio o del titular | `noExp` obligatorio en fichas y citas; `id_paciente` NOT NULL en todas las tablas que migran |
| 2 | Toda búsqueda en la que el usuario ingresa el expediente del titular se queda tal cual. Al **guardar** un dato del paciente se guarda solo `id_paciente` | Las 22 tablas de abajo quedan sin `no_exp`, `pk_num`, `cd_familiar` ni clave provisional. `id_paciente` es interno: nunca se muestra ni se le pide al usuario |
| 3 | Las columnas viejas se congelan y después se borran | Una versión con `no_exp`/`pk_num` sin uso (solo respaldo de lectura); en la siguiente, se borran |

## Cómo se sabe cómo se registró, sin columnas extra

Desde `id_paciente` se llega a `cns_paciente` (y a `cns_identificador_paciente`), donde la llave
vive **una sola vez**:

| En `cns_paciente` | Significa |
|---|---|
| `pk_num = 0` | Titular |
| `pk_num > 0` | Familiar de SERMED |
| `cd_provisional` | Recién nacido provisional |
| `cd_familiar` | Familiar del legado |
| `no_exp` | El expediente (del titular o propio) |

La historia se lee por persona en un solo JOIN (`patient__person_id = X`), sin respaldo por llave
vieja.

## Cómo viaja el paciente (decisión del 2026-10-27)

`pkNum` no se sobrecarga con otros identificadores (clave provisional, `cd_familiar`): el frontend
manda **`idPaciente`** (interno, nunca se muestra).

1. La búsqueda por expediente devuelve cada miembro con su `idPaciente`, o `null` si nunca se
   atendió. El provisional siempre lo trae.
2. Al elegir un miembro sin `idPaciente`: `POST /visits/patient-open {noExp, pkNum}` (pkNum = el de
   SERMED, 0 = titular) lo abre por la puerta central y devuelve su `idPaciente`.
3. Todo lo que guarda o lee datos del paciente recibe solo `idPaciente`.

Cada bloque: el backend acepta `idPaciente` (y temporalmente la llave vieja), cambia la pantalla,
se quita la forma vieja.

## Qué NO se modifica

Ver [contraer-llave-paciente-tablas-sin-cambio.md](contraer-llave-paciente-tablas-sin-cambio.md)
(**pendiente de revisión por el usuario**).

## Qué migra a `id_paciente` (inventario del 2026-10-27)

Usos de `no_exp`/`pk_num` en código de producción (sin tests ni migraciones):

| Bloque | Módulo | Tablas | Archivos principales (usos) |
|---|---|---|---|
| **C0** ✅ | Entrada | — | `idPaciente` en la búsqueda de miembros, `POST /visits/patient-open`, conversión única `consulta_medica/services/paciente_entrada.py` (`noExp` ya era obligatorio al crear fichas y citas) |
| **C1** | Recepción | `rcp_visits`, `citas_medicas` | `repositories/citas_repository.py` (28), `repositories/visit_repository.py` (28), `uses_case/visit_queue_usecase.py` (23), `uses_case/qr_checkin_usecase.py` (22), `services/vigencia_service.py` (21), `views/citas_views.py` (19), `services/ficha_service.py` (12), `views/__init__.py` (11), `services/clinica_paciente_service.py` (8), `impresion/ficha.py` (6) |
| **C2** | Somatometría | `smt_visit_vitals`, `smt_patient_latest_vitals` | `repositories/vitals_repository.py` (29), `uses_case/capture_vitals_usecase.py` (10) |
| **C3** | Consulta médica | `cns_allergy`, `cns_medical_leave`, `cns_study_result`, `cns_stomatology_history`, `cns_odontograma`, `cns_clinical_history`, `cns_antecedente_personal`, `cns_antecedente_familiar`, `cns_antecedente_quirurgico`, `cns_habito`, `cns_tratamiento_dental` | `views.py` (220), `views_unified_history.py` (99), `uses_case/patient_record_usecase.py` (63), `services/patient_link_service.py` (61), `repositories/clinical_history_repository.py` (42), `repositories/allergy_repository.py` (24), `repositories/medical_leave_repository.py` (22), `repositories/odontogram_repository.py` (22) y el resto de `uses_case/` y `repositories/` (≈15 archivos, < 20 usos cada uno) |
| **C4** | Otros módulos | `cir_surgery`, `hsp_admission`, `amb_request`, `ref_referral`, `contratos_oxigeno` | `pases/repositories/referral_repository.py` (24), `contratos_oxigeno/derechohabiente_service.py` (14), `cirugias/repositories/surgery_repository.py` (12), `ambulancias/repositories/ambulance_request_repository.py` (12) y sus vistas/casos de uso |
| **C4b** | Padrones | `cns_padron_cronico`, `cns_padron_discapacidad` | `padrones/uses_case/padron_usecase.py` (24), `padrones/views.py` (12), `padrones/models.py` (10) |
| **C5** | Impresión y reportes | — | `impresion/services/patient_header.py` (35), `impresion/uses_case/print_document_usecase.py` (8), `consulta_medica/impresion/*`, `*/services/report_export_service.py`: el expediente se toma de `cns_paciente` por JOIN |
| **C6** | **Congelar** | las 22 de C1–C4b | `id_paciente` NOT NULL; el código deja de escribir `no_exp`/`pk_num` (columnas a NULL permitido, sin uso); se retira la doble escritura (`operational_link_service`, `patient_link_service._link_on_save`) y el respaldo por llave vieja de `for_patient` |
| **C7** | **Borrar** (versión siguiente) | las 22 de C1–C4b | Migración que elimina `no_exp`/`pk_num` de esas tablas, con respaldo previo |

Tamaño de referencia: unos 100 archivos de backend tocan la llave; los de las tablas que no se
modifican no cambian. El impacto en el frontend depende de cómo viaje el paciente elegido después
de la búsqueda (se define en C0); el expediente que se muestra en pantalla sale de `cns_paciente`.

## Cómo se trabaja cada bloque

1. La entrada resuelve el paciente elegido a su `id_paciente` y pasa `patient` al caso de uso.
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

- **Achicar el rango del provisional:** mientras alguna pantalla o API lleve el `cd_provisional` en
  `pkNum`, con números chicos chocaría con un `PK_NUM` real. Se revisa al definir C0.
- Las tablas de [contraer-llave-paciente-tablas-sin-cambio.md](contraer-llave-paciente-tablas-sin-cambio.md).


## C6 — checklist de ejecución (inventario del 2026-10-27)

Regla: después de C6 ninguna de las 22 tablas guarda `no_exp`/`pk_num`; todo se filtra y se crea por
`patient` y lo que se muestra sale de `cns_paciente` (`llave_publica`).

**A. Filtros que pasan a `cns_paciente`**
- [x] `ambulancias/repositories/ambulance_request_repository.py` (filtro por expediente)
- [x] `cirugias/repositories/surgery_repository.py` (filtro por expediente)
- [x] `consulta_medica/repositories/medical_leave_repository.py` (filtro por expediente)
- [x] `padrones/uses_case/padron_usecase.py` (expediente + pkNum)
- [x] `pases/repositories/referral_repository.py` (por paciente y por expediente)
- [x] `consulta_medica/uses_case/consultation_usecase.py` (`id_visit__no_exp/pk_num` → `id_visit__patient_id`)
- [x] `consulta_medica/uses_case/odontogram_usecase.py`, `patient_record_usecase.py` (la visita es del paciente)
- [x] `consulta_medica/services/patient_link_service.py`: `for_patient` sin respaldo por llave vieja; `keys_for_person`
- [x] `consulta_medica/repositories/consultation_repository.py`

**B. Creaciones que pasan `patient` explícito** (la señal ya no puede resolverlo desde la llave)
- [x] hijos de la visita: `follow_up_usecase`, `medical_leave_usecase`, `study_result_usecase`, `pases/referral_usecase`
- [x] por llave de la URL: `allergy_repository`, `medical_leave_repository`, `odontogram_repository`,
      `stomatology_history_repository`, `study_result_repository`, `clinical_history_repository`,
      `patient_record_usecase`, `pases/referral_repository`, `citas_repository`, `visit_repository`,
      cirugías, ambulancias, padrones, contratos
- [x] `get_or_create` por llave (estomatología, historia clínica, odontograma) → por `patient`

**C. Lecturas de la fila** → `llave_publica`: `consulta_medica/views.py`, `impresion/*`, `*/impresion/*`,
`report_export_service`, `record_access_audit_service`.

**D. Congelar**
- [x] Señales: resuelven `patient` si llega la llave y **vacían** `no_exp`/`pk_num` antes de guardar
- [x] Migraciones: `no_exp`/`pk_num` con NULL permitido y sin default en las 22 tablas; `id_paciente` NOT NULL
      (salvo `portal_miembros`, fuera de alcance)
- [x] Suite completa de todas las apps en verde

**Resultado C6 (2026-10-27):** suite completa en verde (consulta_medica 641, resto de apps 1574).
Migraciones, en este orden: `*_llave_vieja_opcional` → `consulta_medica.0065_completar_id_paciente`
(completa id_paciente con `link_existing`) → `*_id_paciente_obligatorio`.

**Pendiente para C7** (versión siguiente, con respaldo previo):
- Borrar `no_exp`/`pk_num` (`expediente` en contratos) de las 22 tablas, con sus índices y únicos viejos.
- Quitar el respaldo por llave vieja de `for_patient` y la copia en `keys_for_person`.
- Retirar los importadores masivos del legado y `corregir_llave_familiares_legacy`
  (sus 2 tests quedaron omitidos: movían filas cambiando la llave).
- Quitar la aceptación transitoria de `noExp`/`pkNum` en los serializers que ya reciben `idPaciente`.
