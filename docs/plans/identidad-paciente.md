# Plan: identidad única del paciente (persona + afiliaciones)

> Estado: **Fase 0 en curso** (2026-10-22). Las decisiones de diseño se acordaron
> con el usuario en la conversación del 2026-10-22; este archivo es el plan de
> implementación y el inventario de la Fase 0. El documento de diseño detallado se
> escribe aparte, cuando el usuario lo pida.

## Objetivo

Que cada persona tenga **una sola historia clínica visible**, aunque haya sido
atendida como hijo, como trabajador o como recién nacido provisional, sin mover ni
duplicar registros y sin romper la aplicación en ningún paso.

## Decisiones acordadas (resumen)

| Tema | Decisión |
|---|---|
| Enfoque | Registros por afiliación + identificador de persona (vínculo, patrón EMPI) |
| `id_paciente` | 1 afiliación = 1 registro de `cns_paciente`, siempre. Nunca duplicados de la misma afiliación |
| `id_persona` | Tabla nueva `cns_persona` (uuid NOM-024); `cns_paciente.id_persona` NOT NULL. Vincular = mismo `id_persona` (reversible, con bitácora) |
| Identificadores | `NO_EXP`, `PK_NUM`, `CD_FAMILIAR` (CURP solo para detectar coincidencias) |
| Recién nacido | `cns_paciente` con `cd_familiar` de una secuencia por encima del máximo del legado + `PACIENTE_PROVISIONAL` (`sw_status`, madre, orden de nacimiento, clínica, vigencia) |
| Tablas operativas y citas | `id_paciente` (el registro atendido, no la persona). `pk_num` nullable y sin 0 por defecto |
| Cuándo nace el registro | Al iniciar o capturar cualquier cosa del paciente. Historia clínica en la primera consulta |
| Sin fantasmas | Una función central de alta: verifica contra SERMED, normaliza `no_exp`, segura ante concurrencia |
| Coincidencias | CURP (fuerte); nombre + fecha + sexo (débil). Solo personal, confirmación con un clic |
| Lecturas clínicas | Siempre por persona, con origen de cada dato y alerta de contradicciones |
| Sexo | `M`/`F`/`X`; desde la CURP `H→M`, `M→F`, `X→X`. Fecha de corte documentada (la bitácora inmutable conserva el significado viejo) |
| Vigencia | La de Capital Humano; recién nacido provisional: hoy + 60 días (parámetro; legado `ope_param.no_diasvig` de la clínica 7) |
| Legado | Copia tal cual en esquema `legado` (solo lectura) → archivo de eventos aislado → hechos permanentes en el modelo nuevo con origen "legado". Retención: archivar, nunca borrar |

## Técnicas para no romper la aplicación

1. **Expandir → migrar → contraer**: primero se agrega (opcional), después se llena y
   se adapta el código, al final se quita lo viejo.
2. **Doble escritura** durante la transición (lo viejo y lo nuevo a la vez).
3. **Interruptores** en `settings.IDENTIDAD_PACIENTE`, apagados por defecto.
4. **Modo observación** antes de aplicar reglas nuevas.
5. **Verificación por fase**: tests, SQL en el servidor, respaldo previo, reversa documentada.

Una sola fase abierta a la vez.

## Fases

| # | Fase | Tamaño | Depende de |
|---|---|---|---|
| 0 | Preparación: inventario, interruptores, prueba de concurrencia | S | — |
| 1 | Función central de alta (modo observación → bloqueo de fantasmas) | M | 0 |
| 2 | Sexo: `cd_sexo` de familiares en la sync; convención M/F/X | M | 1 |
| 3 | `cns_persona` (expandir, llenar 1:1 conservando el uuid, contraer) | M | 1 |
| 4 | Lecturas clínicas por persona (resultados idénticos hoy) | L | 3 |
| 5 | `id_paciente` en las 10 tablas operativas, tabla por tabla | L | 1 |
| 6 | Recién nacido provisional | M | 5 (citas y visitas) |
| 7 | Vinculación (detección, confirmación, descarte) | L | 4, 6 |
| 8 | Legado en tres capas (puede correr en paralelo desde la 3) | L | 3 |
| 9 | Cierre: concurrencia en Postgres, runbook, retirar interruptores | S | todas |

**Definición de terminado:** un recién nacido se registra, se atiende, aparece en
SERMED, se vincula con un clic y el médico ve toda su historia en un solo lugar,
sin duplicados y con todo en la bitácora.

---

## Fase 0 — Inventario

### A. Dónde nace un paciente (`cns_paciente`)

Todo pasa hoy por **`PatientRepository.get_or_create(no_exp, pk_num)`**
(`consulta_medica/repositories/clinical_history_repository.py:35`), salvo dos
excepciones. La Fase 1 convierte ese punto en la función central.

| Punto de entrada | Archivo | Observación |
|---|---|---|
| Abrir historia clínica / ficha / grupo sanguíneo | `consulta_medica/uses_case/clinical_history_usecase.py:84,90,98`, `blood_type_usecase.py:58` | Vía `ClinicalHistoryRepository.get_or_create_for_patient` |
| Historia de estomatología / odontograma | `stomatology_history_usecase.py:43,52`, `repositories/odontogram_repository.py:65` | Vía `StomatologyHistoryRepository` → mismo camino |
| Padrones (crónicos, discapacidad) | `padrones/uses_case/padron_usecase.py:215` | Llama directo a `PatientRepository.get_or_create` |
| Vinculación de registros clínicos (7b) | `consulta_medica/services/patient_link_service.py:105` (`link_existing`) | ⚠️ **Crea pacientes sin verificar contra SERMED** (`create_missing=True`) |
| Importación del legado | `services/legacy_history_import_service.py:150,203,248`, `commands/migrar_historial_clinico_legacy.py:197` | Crean por llave del legado (a propósito) |
| Corrección de llave de familiares | `services/family_key_fix_service.py:182,198` | **Excepción:** `Patient.objects.create` directo |

**Ninguno verifica hoy que el `no_exp`/`pk_num` exista en SERMED** (origen posible
de pacientes fantasmas) **ni normaliza el `no_exp`** (`"40041"` y `" 40041"` son
dos registros para la restricción única).

### B. Patrón existente que se reutiliza (etapas 7a–7e)

Las 21 tablas clínicas ya pasaron por expandir → doble escritura → leer:
- `id_paciente` nullable (migración `consulta_medica.0044`);
- `vincular_id_paciente` llena lo existente;
- señal `pre_save` (`_link_on_save`) resuelve `id_paciente` al guardar (no crea pacientes);
- `for_patient()` centraliza las lecturas.

La Fase 4 parte de `for_patient()` y la Fase 5 repite este patrón en las tablas operativas.

### C. Tablas operativas que identifican por `(no_exp, pk_num)`

| Tabla | Modelo | Dónde se crean filas | `pk_num` |
|---|---|---|---|
| `contratos_oxigeno` | `ContratoOxigeno` | `contratos_oxigeno/views.py` (`ModelViewSet` + serializer) | int, default 0 |
| `amb_request` | `AmbulanceRequest` | `ambulancias/repositories/ambulance_request_repository.py:21` | int, default 0 |
| `ref_referral` | `Referral` | `pases/repositories/referral_repository.py:35` | int, default 0 |
| `cir_surgery` | `SurgerySchedule` | `cirugias/repositories/surgery_repository.py:54` | int, default 0 |
| `hsp_admission` | `HospitalAdmission` | `hospitalizacion/repositories/hospital_admission_repository.py:68` (`save()`) | int, default 0 |
| `smt_visit_vitals` | `VisitVitalSigns` | `somatometria/repositories/vitals_repository.py:44` | int, default 0 |
| `smt_patient_latest_vitals` | `PatientLatestVitals` | `somatometria/repositories/vitals_repository.py:100` | int, default 0 |
| `citas_medicas` | `CitaMedica` | `recepcion/repositories/citas_repository.py:290`, `portal_citas/uses_case/reservar_cita_usecase.py:207` | int (era smallint, ver D.1), default 0 |
| `rcp_visits` | `Visit` | `recepcion/repositories/visit_repository.py:34` | int, default 0 |
| `portal_miembros` | `PortalMiembro` | `portal_citas/uses_case/iniciar_sesion_usecase.py:54`, `capturar_correo_usecase.py:37`, `services/nucleo_service.py:137` | int, default 0 |

Orden propuesto para la Fase 5 (de menor a mayor riesgo): contratos de oxígeno,
ambulancias, pases → cirugías, hospitalización → signos vitales → citas, visitas, portal.

Bitácoras que **no se tocan** (evidencia de su momento): `bitacora_acceso`,
`imp_bitacora_impresion`, `cns_conflicto_migracion`, `solicitudes_arco`.

### D. Hallazgos de la Fase 0

1. ⚠️ **Bug vigente: `citas_medicas.pk_num` es `smallint`** (máximo 32 767). Los
   `PK_NUM` de SERMED son mayores (p. ej. 48411). En Postgres, agendar una cita para
   esos familiares falla con `smallint out of range`. Las visitas tuvieron el mismo
   problema y se corrigió en `recepcion.0006_visit_pknum_smallint_to_int`; las citas
   quedaron sin corregir. Los tests no lo detectan porque corren en SQLite.
   ✅ **Corregido** con aprobación del usuario (commit `2429c16`, migración
   `recepcion.0027`). `recepcion/tests/test_pk_num_tipo.py` impide que cualquier
   `pk_num` vuelva a ser smallint.
2. Todas las tablas operativas tienen `pk_num` con **0 por defecto, y 0 = titular**:
   un registro sin `pk_num` queda a nombre del trabajador. Se corrige en la Fase 5.
3. `link_existing` crea pacientes sin verificar contra SERMED: se cubre en la Fase 1.

### E. Interruptores (todos apagados)

En `backend/config/settings.py`, `IDENTIDAD_PACIENTE`:

| Variable de entorno | Valores | Fase |
|---|---|---|
| `IDENTIDAD_VERIFICAR_SERMED` | `apagado` (default) / `observar` / `bloquear` | 1 |
| `IDENTIDAD_LECTURA_OPERATIVA_POR_ID` | `False` (default) / `True` | 5 |
| `IDENTIDAD_RECIEN_NACIDOS` | `False` (default) / `True` | 6 |
| `IDENTIDAD_VINCULACION` | `False` (default) / `True` | 7 |

### F. Prueba de concurrencia en Postgres

Los tests normales corren en SQLite, que no reproduce la concurrencia de Postgres.
`apps/consulta_medica/tests/test_concurrencia_paciente.py` (etiqueta `postgres`) se
salta en SQLite y se corre en el servidor contra una base de prueba descartable:

```bash
docker compose exec -e TESTS_EN_POSTGRES=1 backend \
  python manage.py test apps.consulta_medica.tests.test_concurrencia_paciente --tag=postgres --noinput
```

Django crea y destruye su propia base `test_<nombre>`: **no toca los datos reales**.
El usuario de Postgres necesita permiso para crear bases (el de la imagen oficial lo tiene).
