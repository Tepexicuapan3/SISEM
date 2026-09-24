# Runbook: Migración de datos `his_hospital` (legado) → `hsp_admission` (SIRES)

> TL;DR: este documento es SOLO el mapeo columna-por-columna y el orden de operaciones. El
> esquema (modelos, migraciones, protección NOM-024) ya está implementado (change
> `his-hospital-modelo-nom024`). La carga de las ~31,967 filas reales es responsabilidad del
> usuario — no hay ETL ni management command de importación masiva en este change (alcance
> explícitamente excluido, ver Engram `sdd/his-hospital-modelo-nom024/proposal`).

## Problem / Context

`his_hospital` (dump `Dump20260903.sql`, MySQL, `latin1_spanish_ci`) es la bitácora de ingresos y
altas hospitalarias del legado (~31,967 filas reales, `AUTO_INCREMENT=31968`). El nuevo modelo
Postgres es `apps.hospitalizacion.models.HospitalAdmission` (`db_table="hsp_admission"`), con
versionado append-only vía `HospitalAdmissionRevision` (protección NOM-024-SSA3).

## Orden de operaciones OBLIGATORIO

No saltear pasos ni cambiar el orden — cada uno es prerequisito físico del siguiente.

1. `python manage.py migrate catalogos 0028` — crea `CatTipoHospitalizacion` (23 filas) y
   `CatTipoAlta` (6 filas).
2. `python manage.py migrate catalogos 0029` — agrega `legacy_cd_clinica` a
   `CatCentroAtencion` (columna física real, verificar con introspección si hay dudas —
   `CatCentroAtencion` es `managed=False`, ver nota abajo).
3. `python manage.py migrate hospitalizacion` — crea `hsp_admission` / `hsp_admission_revision`.
4. `python manage.py seed_catalogos_hospitalizacion --confirm` — siembra los 29 valores de
   catálogo (correr primero sin `--confirm` para ver la vista previa).
5. **Prerequisito del usuario**: los médicos hospitalarios deben tener `CatMedico.legacy_cd_medico`
   poblado (carga manual por Excel, ya establecida en el proyecto). Sin esto, `admitting_doctor`/
   `discharge_doctor` quedan `NULL` en la carga (el código crudo se conserva, se puede resolver
   después).
6. **Prerequisito del usuario**: mapear `cat_clinicas.cd_clinica` (int, legado) → `CatCentroAtencion`
   completando `legacy_cd_clinica` en las ~14 clínicas existentes (trabajo manual chico).
7. Carga de las ~31,967 filas de `his_hospital` → `hsp_admission`, con la tabla de mapeo de abajo.
   Esto es trabajo del usuario, fuera de este change.
8. `HospitalAdmission.resolve_pending_fk()` ×3 (una vez por cada FK diferida: `admitting_doctor`,
   `discharge_doctor`, `origin_center`). Usar el wrapper de use-case
   `apps.hospitalizacion.uses_case.hospital_admission_usecase.resolve_pending_fk(field=..., code_field=..., lookup=...)`,
   que además deja un `AuditoriaEvento` (`accion="hsp_admission.resolve_pending_fk"`) — NO genera
   `HospitalAdmissionRevision` (es carga de datos, no edición).

### Nota sobre `CatCentroAtencion` y `managed=False`

`CatCentroAtencion` es `managed=False` en Django: un `AddField` normal en una migración
actualizaría el estado de Django pero NO emitiría el `ALTER TABLE`. La migración
`catalogos/0029_catcentroatencion_legacy_cd_clinica.py` ya resuelve esto con
`SeparateDatabaseAndState` (mismo patrón que `catalogos/0015_reconcile_catcentroatencion_drift.py`),
así que el paso 2 de arriba deja la columna físicamente creada. No hace falta ninguna acción manual
extra, solo correr la migración.

## Rollback

`manage.py migrate hospitalizacion zero` + `manage.py migrate catalogos 0027`. La reversa de la
migración 0029 es intencionalmente un no-op (no borra `legacy_cd_clinica`: podría tener datos
reales cargados). **Punto de no retorno: el paso 7 (carga de datos).** El rollback después de
cargar datos los borra — decidir go/no-go ANTES de ese paso.

## Tabla de mapeo: MySQL `his_hospital` → Postgres `hsp_admission`

PK del legado `no_hservicio`. **NO se reutiliza como PK** — `hsp_admission.id_ingreso` es un
`bigserial` propio de Postgres.

| # | Columna MySQL | Tipo MySQL | Campo Postgres | Columna PG | Tipo PG | Transformación / notas |
|---|---|---|---|---|---|---|
| — | — | — | `id` | `id_ingreso` | `bigserial` PK | Generado por Postgres. |
| 1 | `no_hservicio` | `int unsigned` AI PK | `legacy_folio` | `folio_legado` | `varchar(20)` UNIQUE NULL | `CAST(no_hservicio AS char)`. Identidad de la fila legado → NO versionado, NO editable. |
| 2 | `no_exp` | `int unsigned` NOT NULL | `no_exp` | `no_exp` | `varchar(20)` INDEX | `CAST(... AS char)` — `no_exp` es `CharField(20)` en todo SIRES. |
| 3 | `tp_paciente` | `varchar(10)` NOT NULL | `pk_num` | `pk_num` | `integer` DEFAULT 0 | `int(tp_paciente or 0)`. `0`=titular, `>0`=`cat_familiar.pk_num`. Fila con valor no numérico → descartar y reportar. |
| 4 | `cd_shosp` | `varchar(20)` NULL | `hospital_service_folio` | `folio_servicio` | `varchar(20)` NULL | Directo. **El COMMENT miente**: dice "CLAVE DEL HOSPITAL" pero los datos son folios (`HH12-2`, `EH16-6391`). NO crear FK con esto. |
| 5 | `cd_tphospi` | `int unsigned` NOT NULL | `admission_type` (FK) | `id_tipo_hospitalizacion` | `bigint` FK NULL | JOIN `cat_tipo_hospitalizacion.legacy_code`. Seed primero (paso 4, 23 filas). |
| 6 | `ds_motivo` | `varchar(3000)` NOT NULL | `reason` | `motivo` | `text` | Directo. **Reencodear `latin1_spanish_ci` → UTF-8** (exportar con `--default-character-set=latin1`). |
| 7 | `fe_ingreso` | `date` NOT NULL | `admission_date` | `fecha_ingreso` | `date` INDEX | Directo. `'0000-00-00'` es válido en MySQL e inválido en Postgres → descartar/reportar. |
| 8 | `hh_ingreso` | `varchar(10)` NOT NULL | `admission_time` | `hora_ingreso` | `time` NULL | `'HH:MM'` → `TIME`. Vacío/basura → `NULL` (por eso el campo es nullable aunque MySQL diga NOT NULL). |
| 9 | `cd_medicoing` | `int(10)` NOT NULL | `admitting_doctor` (FK) + `admitting_doctor_code_legacy` | `id_medico_ingreso`, `clave_medico_ingreso_legado` | `bigint` FK NULL, `varchar(10)` | Crudo SIEMPRE (`CAST AS char`). FK: JOIN `cat_medicos.legacy_cd_medico` (comparar como texto). Sin match → FK NULL, crudo preservado, resolver luego con `resolve_pending_fk()`. |
| 10 | `fe_registroing` | `datetime` NOT NULL | `registered_at` | `fch_registro_ingreso` | `timestamptz` NULL | Directo. Timestamp de CAPTURA, distinto de `fe_ingreso` (puede haber captura diferida). No versionado. |
| 11 | `cd_usuarioing` | `varchar(20)` NOT NULL | `registered_by_code_legacy` | `clave_usuario_ingreso_legado` | `varchar(20)` NULL | Solo texto crudo, SIN FK. Valores mixtos (username / no. de empleado) de `cat_usuarios` (DBSIIM, otra base) — irrecuperable como FK. |
| 12 | `cd_snota` | `varchar(20)` NULL | `clinical_note_code_legacy` | `folio_nota_legado` | `varchar(20)` NULL | Crudo. Liga a `his_notas` → `LegacyConsultationRecord.legacy_folio`, resoluble después. Casi siempre `NULL` en los datos reales. |
| 13 | `fe_alta` | `date` NULL | `discharge_date` | `fecha_alta` | `date` NULL | Directo. `NULL` = sin alta registrada (frecuente). **Campo que el legado pisa in-place** (`body-altaing.jsp:410`) → el que más importa versionar en SIRES. |
| 14 | `hh_alta` | `varchar(10)` NULL | `discharge_time` | `hora_alta` | `time` NULL | Igual que #8. |
| 15 | `cd_medicoalta` | `int unsigned` NULL | `discharge_doctor` (FK) + `discharge_doctor_code_legacy` | `id_medico_alta`, `clave_medico_alta_legado` | `bigint` FK NULL, `varchar(10)` | Igual que #9. **Confirmado**: resuelve contra `cat_medicos.legacy_cd_medico`, NUNCA contra `SyUsuario` (el COMMENT del dump está equivocado). |
| 16 | `sw_programado` | `varchar(1)` NOT NULL | `is_scheduled` | `es_programado` | `boolean` DEFAULT false | `'S'→true`, `'N'→false`. |
| 17 | `sw_status` | `varchar(1)` NOT NULL | `is_active` (+ `deleted_at`) | `est_activo`, `fch_baja` | `boolean` DEFAULT true, `timestamptz` NULL | `'A'→true`, `'B'→false`. Si `'B'`: setear también `deleted_at`. **Soft-delete: JAMÁS omitir la fila** (retención NOM-024, 5 años). |
| 18 | `cd_origeno` | `int unsigned` NOT NULL | `origin_center` (FK) + `origin_center_code_legacy` | `id_centro_origen`, `clave_clinica_origen_legado` | `bigint` FK NULL, `integer` | Crudo siempre. FK: JOIN `cat_centros_atencion.legacy_cd_clinica` (columna nueva, migración 0029, paso 2 de este runbook). Valor dominante en los datos reales: `5`. |
| 19 | `no_foliohosp` | `varchar(20)` NULL | `external_folio` | `folio_externo` | `varchar(20)` NULL | Directo. Folio del webservice del hospital externo (ej. `F16563`). |
| 20 | `tp_alta` | `int unsigned` NULL | `discharge_type` (FK) | `id_tipo_alta` | `bigint` FK NULL | JOIN `cat_tipo_alta.legacy_code`. Seed primero (paso 4, 6 filas). |
| — | — | — | `created_at` | `fch_alta` | `timestamptz` | Usar `fe_registroing` en la carga, para no perder la cronología. |
| — | — | — | `updated_at`, `deleted_at` | `fch_modf`, `fch_baja` | `timestamptz` | `NULL` en la carga inicial (salvo `deleted_at` si `sw_status='B'`, ver #17). |
| — | — | — | `created_by_id`/`updated_by_id`/`deleted_by_id` | `usr_alta`/`usr_modf`/`usr_baja` | `bigint` NULL | `NULL` en la carga — no hay puente de usuario (ver #11). |

## Valores de catálogo sembrados por `seed_catalogos_hospitalizacion`

Verificados directamente contra el dump (`INSERT INTO cat_tphospi/cat_tpaltas VALUES ...`).

**`CatTipoHospitalizacion`** (`legacy_code` = `cd_tphospi`, 23 filas, todas `sw_status='A'`):
1 Atención en urgencias · 2 Corta estancia · 3 Cirugía · 4 Hospitalización · 5 Maternidad ·
6 Endoscopia · 7 PH metría · 8 Manometría · 9 Colonoscopía · 10 Cistoscopía · 11 Litotripsia ·
12 Inhaloterapia · 13 Hemodiálisis · 14 Estudio laboratorio · 15 Estudio gabinete ·
16 Quimioterapia · 17 Radioterapia · 18 Urodinamia · 19 Cistografía · 20 Colocación catéter ·
21 Doble JJ · 22 Estudio anatomía patológica · 23 Control térmico.

**`CatTipoAlta`** (`legacy_code` = `tp_alta`, 6 filas, todas `sw_status='A'`):
1 Alta voluntaria · 2 Alta médica (por mejoría y/o curación) · 3 Alta por traslado a otra unidad ·
4 Alta por defunción · 5 Alta por máximo beneficio · 6 Alta.

> Nota: el valor 5 del legado viene literalmente como `"ALTA POR MAXIMO BENEFICIO)"` (paréntesis de
> cierre sin apertura, error de captura evidente comparado con el valor 2). El seed corrige el
> typo tipográfico en el `name` mostrado; el `legacy_code` (la clave real del JOIN) queda intacto.

## Campos del legado SIN equivalente (pérdida ya ocurrida en el legado)

- **`fe_registroalta` / `cd_usuarioalta` no existen en `his_hospital`.** El cuándo/quién capturó el
  ALTA es irrecuperable para las ~31,967 filas históricas. Consecuencia: las filas importadas
  llegan **sin revisiones previas** — el historial de cambios de `HospitalAdmissionRevision`
  arranca recién en el momento de la carga, no antes.
- **`cd_usuarioing` no tiene puente a `SyUsuario`** (valores mixtos username/no. de empleado de
  `cat_usuarios`, base DBSIIM). Queda como texto crudo (`registered_by_code_legacy`), no editable.
- **Estancia (días de internamiento)** no existe como columna — se deriva en el modelo con la
  propiedad `HospitalAdmission.length_of_stay_days` (`discharge_date - admission_date`).
- **Cama**: existe `body-asignacama.jsp` en el legado, pero `his_hospital` no tiene ninguna columna
  de cama en sus 20 campos — vive en otra tabla, fuera de alcance de este change.

## Advertencias operativas

| Riesgo | Mitigación |
|---|---|
| Horas `varchar` con basura rompen el `CAST` a `TIME` | Campos `*_time` son nullable; validar y reportar las filas que no parsean antes de insertar. |
| `latin1_spanish_ci` mal convertido → mojibake en `ds_motivo` | Exportar con `--default-character-set=latin1` y reencodear a UTF-8 explícitamente. |
| Cargar sin catálogos/médicos/`legacy_cd_clinica` primero → FK `NULL` masivas | Respetar el orden de la sección "Orden de operaciones" al pie de la letra. |
| Omitir filas `sw_status='B'` | Prohibido: se cargan con `is_active=false`, nunca se descartan (retención NOM-024, 5 años). |
| `'0000-00-00'` en `fe_ingreso` | MySQL lo permite, Postgres no — descartar la fila y reportarla, no forzar un valor. |
