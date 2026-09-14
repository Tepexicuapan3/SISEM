# Continuar en la PC del trabajo — estado al 2026-09-14 (actualizado, misma fecha)

> TL;DR: esta sesión migró la **historia clínica real del legado** (3385
> pacientes), corrigió catálogos mal cargados, versionó `ClinicalHistory` y
> agregó **nota de aclaración post-cierre** de consultas (dos gaps de
> NOM-024/004 cerrados), conectó el header del expediente a datos reales
> (ya no muestra el mock "María Guadalupe"), agregó el selector
> titular/derechohabiente que faltaba en el expediente, y construyó el
> **frontend completo del Portal de Citas** (login OTP + ver/reservar/
> cancelar citas) que antes solo existía como backend. Todo corrido contra
> el Postgres de **desarrollo** (`50.192.41.223`, confirmado que NO es
> producción). Sigue sin commitear — revisar `git status` antes de seguir.

## Cómo usar este documento

1. Lee "Bloqueado" primero: son las cosas que precisamente necesitan la
   red del trabajo (acceso a Oracle/MySQL legado).
2. "Completado" es para no repetir trabajo ni re-preguntar qué ya existe.
3. "Pendiente de decisión" necesita que el usuario (no el asistente)
   defina algo antes de tocar código.

## Completado HOY (historia clínica + NOM-024 + Portal de Citas)

### Migración real de historia clínica (`his_clinica` → `ClinicalHistory`)
- **3385 historias clínicas migradas de verdad** contra el Postgres de
  desarrollo, desde el dump real `Dump20260903.sql` (ya no está bloqueado
  por falta de backup — el backup llegó y se usó).
- Comando `backend/apps/consulta_medica/management/commands/migrar_historial_clinico_legacy.py`
  (ya existía, tenía bugs nunca ejercitados contra datos reales — corregidos):
  `no_exp` es `int` en el legado no `str`; normalización de catálogos
  ahora tolera acentos/espacios faltantes; transacción por fila con
  manejo de errores (antes una fila mala tiraba abajo todo el proceso).
- `ClinicalHistory.phone` ampliado de 15 a 50 caracteres — el legado
  guarda `"cel XX-XXXX-XXXX tel XXXX-XXXX ext XXXXX"` (40 chars) en el
  **100%** de los registros, no un caso raro.
- Catálogo `Ocupaciones` corregido: tenía 5 valores mal cargados a mano
  (roles de personal médico) en vez de ocupación civil del paciente —
  comando nuevo `backend/apps/catalogos/management/commands/seed_catalogos_historia_clinica.py`
  (preview + `--confirm`) que también completó `EdoCivil`/`Religion`/
  `TipoResidencia` (estaban incompletos o vacíos).
- **`his_notas` también migrado** (604,178 notas históricas, 0 errores) —
  NO a `VisitConsultation` (eso hubiera requerido crear 604k `Visit`
  sintéticas, contaminando el modelo operativo en vivo): se creó
  `consulta_medica.LegacyConsultationRecord`, un archivo de **solo
  lectura** separado, sin enlace a `Visit`. Hallazgo real: el CIE-10
  "principal" (`no_cie`) está vacío en el 100% de los registros — el
  diagnóstico real vive como texto libre (`diagnostic_impression`, 99.3%
  de cobertura) y el código estructurado depende 100% de `det_hisnotcie`
  (8+ millones de filas, sigue sin migrar — ver pendientes). Rango real
  del dump: solo 2025-01 a 2026-09 (17,426 pacientes distintos); el
  histórico 2015-2024 vive en las bases anuales archivadas del legado,
  no en este dump. Tampoco se tocó `his_clinicad` (odontología, tabla
  aparte).
- **Frontend del historial legado también construido**: endpoint
  `GET /patients/<no_exp>/legacy-consultations` + sección colapsable
  "Historial previo a SIRES" en `ExpedienteHistorialTab.tsx` (ver
  `LegacyConsultationHistorySection.tsx`), debajo de las consultas reales
  de SIRES. Solo lectura, sin acciones — coherente con que es un archivo
  histórico inmutable.

### NOM-024 — dos gaps de integridad clínica cerrados
1. **`ClinicalHistory` ahora versiona ediciones** (`ClinicalHistoryRevision`,
   migración `0019`) — mismo patrón que `VisitConsultationRevision`, con
   el matiz de que solo versiona cuando un valor YA concreto se
   sobreescribe (rellenar un campo vacío por primera vez no cuenta,
   `ClinicalHistory` es incremental por diseño).
2. **Nota de aclaración post-cierre de consultas** (`ConsultationAddendum`,
   migración `0020`, endpoint `GET/POST /visits/<id>/consultation/addenda`)
   — reemplaza el antipatrón del legado `sw_complemento` (se sobrescribía,
   perdía la adenda anterior). Append-only: nunca se edita ni se borra una
   adenda, si hace falta corregir se agrega una nueva. **Frontend también
   construido**: bloque colapsable en `ExpedienteHistorialTab.tsx` (ver
   `ConsultationAddendaSection.tsx`) para ver/agregar aclaraciones por
   consulta.
3. De paso, se corrigió un bug de infraestructura que bloqueaba
   `manage.py test` completo para cualquiera sin Docker (migración
   `medicos/0009` con sintaxis SQL específica de Postgres, incompatible
   con el SQLite que usan los tests) — ahora la suite corre local sin
   Docker.

### Expediente clínico (frontend) — mock reemplazado por datos reales
- `ExpedienteDetailPage.tsx` mostraba un paciente **hardcodeado**
  ("María Guadalupe Hernández Pérez") sin importar qué expediente se
  abriera — nombre/edad/fecha nacimiento/estatus ahora son reales (via
  `usePatientGeneralInfo`, mismo endpoint `/visits/patient-lookup` que ya
  usa Recepción). CURP/sexo/tipo de sangre/teléfono/email/dirección
  quedan en "No disponible" porque no existen en ningún modelo del
  backend todavía (CURP sí existe en `CatEmpleado.curp` pero no hay
  endpoint que lo exponga — pendiente, ver abajo).
- **Selector titular/derechohabiente agregado**: los 6 tabs del
  expediente (Generales, Estomatología, Odontograma, Historial,
  Licencias, Estudios) ya soportaban `pkNum` en el backend, pero
  `ExpedienteDetailPage` nunca lo exponía — siempre mostraba al titular.
  Ahora hay un selector "Núcleo familiar" (mismo patrón visual que ya usa
  Recepción) y se resetea al titular al cambiar de expediente.

### Portal de Citas — frontend construido de cero (backend ya existía completo)
`backend/apps/portal_citas` es un módulo muy completo (login OTP, núcleo
familiar, reserva con locking transaccional, cancelación, comprobante
PDF+QR, integración real con check-in de recepción) pero **no tenía
NINGÚN frontend** — se construyó en 2 etapas:
- **Etapa 1**: login (3 pasos: identidad → correo si es primera vez →
  código OTP) + pantalla "Mis Citas". Cliente HTTP propio
  (`portalClient.ts`, Bearer token, sesión en `sessionStorage` — separado
  del cliente de staff que usa cookies).
- **Etapa 2**: reservar cita (clínica → consultorio → fecha → horario) y
  cancelar (el backend ya calcula `cancelable` por cita).
- Todo el flujo se validó con requests HTTP reales contra un empleado
  real de la base de desarrollo (datos de prueba borrados después).
- Rutas nuevas: `/portal/login`, `/portal/mis-citas`, `/portal/reservar`
  — públicas, fuera del login de staff.

## Bloqueado — necesita algo de la red del trabajo

1. ~~Backup de `his_clinica`~~ **RESUELTO HOY** — ya se migró.
2. **`inspeccionar_oracle.py`** / **`inspeccionar_legado_mysql.py`** —
   nunca se han podido correr contra los servidores reales.
3. ~~Migración de `his_notas`~~ **RESUELTO HOY** — 604,178 notas
   migradas a `LegacyConsultationRecord` (solo lectura, sin tocar
   `Visit`). Sigue pendiente **`det_hisnotcie`** (8+ millones de filas,
   diagnósticos CIE-10 — sin esto, los registros migrados solo tienen
   diagnóstico en texto libre, no codificado) y **`his_clinicad`**
   (odontología, tabla aparte, sin explorar). Mismo backup ya disponible
   (`Dump20260903.sql`).
4. **Migración histórica de `det_cirugia`/`det_ambulancias`** — los
   modelos ya dejan `legacy_folio` listo, sigue sin backup del legado de
   cirugías/ambulancias.
5. Respaldos completos del runbook (`docs/runbooks/legacy-backup-runbook.md`).

## Pendiente de decisión (el usuario define alcance, no el asistente)

- **Ficha del paciente incompleta**: CURP existe en `CatEmpleado.curp`
  pero no hay endpoint que lo exponga (chico). Sexo/tipo de
  sangre/teléfono de contacto/email/dirección **no existen en ningún
  modelo** — hay que definir de dónde salen (¿sincronizar más campos
  desde Oracle? ¿capturarlos en SIRES?) antes de poder mostrarlos.
- **Interoperabilidad HL7/CDA**: nunca se verificó contra el texto
  oficial del DOF si NOM-024 exige un formato de intercambio específico.
- **Segundo catálogo NOM-024**: confirmar con el certificador cuál es.
- **Fase 5 (médicos)**: cerrar la ventana de compatibilidad de IDs
  necesita telemetría real de producción (`WARNING MEDICO_ID_LEGACY_FALLBACK`).
- **`herramientas`, `movimientos`, `opciones`**: apps vacías, sin alcance
  definido.
- **Farmacia**: `domain-map.md` dice "Discovery" pero en realidad YA HAY
  un módulo real (`VacInventario`, inventario de vacunas) sin frontend —
  el doc de arquitectura está desactualizado, corregirlo.
- **Portal de Citas — mejoras futuras** (no bloqueantes): calendario
  visual mensual (hoy es un `<input type="date">` simple), anuncios/
  especialidades del portal (endpoints ya existen, no se consumieron).
- **Cirugías/Ambulancias — mejoras futuras** (sesión anterior, siguen
  pendientes): internamiento hospitalario, calendario visual,
  autorización de ambulancias segmentada por clínica, catálogo de
  horarios de quirófano.
- Correr `python manage.py seed_catalogos_crud_permissions` a mano en el
  próximo deploy (sesión anterior, sigue pendiente).

## Estado del repo

**Sin commitear todavía** — todo lo de hoy (historia clínica, catálogos,
`ClinicalHistoryRevision`, `ConsultationAddendum`, fix de migración
`medicos/0009`, expediente con datos reales + selector de núcleo, portal
de citas completo) está en el working tree. Correr `git status` antes de
seguir para confirmar el alcance exacto antes de armar el commit.
