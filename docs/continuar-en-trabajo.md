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
>
> **Actualización misma fecha**: se agregó el backend completo de
> **Autorización de Recetas** (reemplaza `det_clinicas.pw_autoriza` del
> legado por RBAC real), verificado contra Postgres real. La integración
> **EMA Recetas sigue bloqueada** — solo hay un plan, no se implementó
> nada (instrucción explícita del usuario), esperando que responda 3
> preguntas abiertas (ver sección "Bloqueado").

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

### Autorización de Recetas — backend completo (Autorizadores, primer submódulo)
Reemplaza el antipatrón del legado `det_clinicas.pw_autoriza` (re-ingresar
la contraseña de login para "autorizar") por RBAC real, mismo criterio que
`clinico:ambulancias:authorize`. Alcance acordado con el usuario:
**"solo Recetas, backend primero"** — Autorización de Estudios queda
aparte (falta definir criterio) y frontend queda para una próxima sesión.
- Modelo `consulta_medica.PrescriptionAuthorization` (migración `0023`):
  se crea automáticamente cuando `add_prescription_item` agrega un
  medicamento `cuadro_basico=ESPECIAL` o `is_controlled=True` (criterio ya
  vivía en el catálogo `Medicamentos`, no hubo que inventar nada). Si ya
  hay una solicitud `pendiente`, se actualizan sus conteos en vez de
  duplicar. Cancelar el item que disparó la autorización **no la revierte
  automáticamente** — queda a criterio humano del autorizador.
- 3 endpoints nuevos: `GET prescriptions/authorizations/pending`,
  `POST .../<id>/authorize`, `POST .../<id>/reject` (motivo obligatorio).
  Permiso nuevo `clinico:recetas:authorize` (sexta tanda de
  `navigation_permissions_seed.py`, ya sembrado en Postgres real).
- 10 tests unitarios (todos pasan) + verificación end-to-end contra
  Postgres real (crear receta con medicamento controlado → autorización
  pendiente → autorizar → confirmar estatus).
- **Bug de entorno descubierto y evitado** (no arreglado de raíz):
  `VisitPrescription.items` (`JSONField` sobre `jsonb`) revienta con
  `TypeError: the JSON object must be str, bytes or bytearray, not list`
  en CUALQUIER lectura fresca desde Postgres real (psycopg2 ya deserializa
  el jsonb y Django intenta volver a hacerle `json.loads()`). Nunca se ve
  en tests con SQLite. Se evitó agregando un FK `visit` denormalizado
  directo en `PrescriptionAuthorization` en vez de navegar
  `authorization.prescription.id_visit`. **Sigue latente** para cualquier
  código futuro que necesite leer o borrar `VisitPrescription` por ORM —
  incluso un simple `.delete()` revienta porque el `Collector` de Django
  siempre hace `SELECT *` antes de borrar. Detalle completo en Engram
  (`architecture/prescription-authorization`).
- Suite completa corrida como red de seguridad
  (`apps.consulta_medica` + `apps.recepcion`, 153 tests): 10 fallas, pero
  **confirmado con `git stash` que son 100% preexistentes** — fallan
  igual contra el código limpio, sin ninguno de los cambios de hoy. Todas
  viven en `apps/recepcion/tests/test_checkin_manual_api.py` (módulo QR
  Checkin, no tocado hoy). Detalle en Engram
  (`bugs/test-checkin-manual-api-broken`) — pendiente de investigar si se
  retoma ese módulo.

### Autorización de Recetas — mejoras NOM-024 y funcionalidad para Autorizadores
El usuario pidió explícitamente mejorar el módulo recién construido para
NOM-024 y darle mejor funcionalidad a Autorizadores. Se identificaron 3
gaps reales (no inventados) y el usuario eligió **"los 3 backend,
frontend después"**:
1. **Segregación de funciones**: antes nada impedía que el mismo usuario
   que prescribió un medicamento ESPECIAL/controlado se autorizara a sí
   mismo (aunque tuviera el permiso `clinico:recetas:authorize` por doble
   rol) — exactamente el problema que el legado intentaba resolver con
   `det_clinicas.pw_autoriza`, pero nunca lo garantizaba de verdad. Ahora
   `PrescriptionAuthorization.prescribed_by_id` (denormalizado, migración
   `0024`) se compara contra el actor en `authorize_prescription`/
   `reject_prescription` — error `SELF_AUTHORIZATION_NOT_ALLOWED` (403)
   si coinciden.
2. **Historial de auditoría**: `GET prescriptions/authorizations` nuevo
   (filtros `estatus`/`fechaInicio`/`fechaFin`) — antes solo existía la
   cola de `pending`, así que una vez resuelta una solicitud desaparecía
   de cualquier listado. Necesario para trazabilidad NOM-024 ("quién
   autorizó qué y cuándo").
3. **Notificación de rechazo**: nuevo evento realtime
   `visit.prescription_authorization.rejected` (mismo canal que el resto
   de eventos de visita) — el médico que prescribió ahora se entera si le
   rechazan la receta, antes no había forma de saberlo salvo volver a
   consultarla a mano.
- 14/14 tests unitarios pasan, verificado end-to-end contra Postgres real
  (segregación bloqueando correctamente, historial filtrando bien).
- Suite completa corrida de nuevo (182 tests): aparecieron 2 fallas
  NUEVAS en `apps/realtime/tests/test_visit_stream_events_api.py` — con
  el mismo método de `git stash` se confirmó que también son
  preexistentes (422 en vez de 200 en cierre/cancelación de consulta, sin
  relación a este trabajo). Detalle en Engram
  (`bugs/test-visit-stream-events-broken`).

## Bloqueado — necesita algo de la red del trabajo

1. ~~Backup de `his_clinica`~~ **RESUELTO HOY** — ya se migró.
2. **`inspeccionar_oracle.py`** / **`inspeccionar_legado_mysql.py`** —
   nunca se han podido correr contra los servidores reales.
3. ~~Migración de `his_notas`~~ y ~~`det_hisnotcie`~~ **RESUELTAS HOY** —
   604,178 notas (`LegacyConsultationRecord`) + 529,315 diagnósticos
   CIE-10 (`LegacyConsultationDiagnosis`), 0 errores en ambas. El
   `AUTO_INCREMENT=8036505` de `det_hisnotcie` era un contador histórico
   acumulado, NO el volumen real (529k confirmado por conteo real). 48%
   de los diagnósticos (255,535) son de notas de **2021** archivadas
   fuera del dump — se migraron igual, sin `record` asociado, por
   decisión explícita de no descartar datos reales. Sigue pendiente
   **`his_clinicad`** (odontología, tabla aparte, sin explorar) y
   conectar el CIE-10 migrado al frontend (`LegacyConsultationHistorySection.tsx`
   no lo muestra todavía).
4. **Migración histórica de `det_cirugia`/`det_ambulancias`** — los
   modelos ya dejan `legacy_folio` listo, sigue sin backup del legado de
   cirugías/ambulancias.
5. Respaldos completos del runbook (`docs/runbooks/legacy-backup-runbook.md`).
6. **EMA Recetas (integración externa de farmacia)** — instrucción
   explícita del usuario: **"no implementes, solo haz el plan para
   revisarlo"**. Contrato leído completo
   (`D:\PROYECTOS EN PRODUCCION\INTEGRACION EMA SISEM\20251003.01_STCM_RECETAS .pdf`,
   incluye JWE con `PK_NUM` como parámetro extra). Plan de 5 fases
   presentado en chat, NO guardado como código. Requisito no negociable:
   el flujo interno de recetas actual **nunca debe romperse** — ambos
   flujos (interno + EMA) deben coexistir de forma independiente, con
   fallback automático al flujo interno si EMA no responde o cambia.
   Sigue esperando que el usuario responda:
   - ¿Dónde vive el código de la API .NET Core que ya está en producción
     mandando la receta?
   - ¿A quién le manda hoy esa API los datos de emisión/cancelación?
   - ¿Recuperar el módulo de java-main que quedó inutilizable está en
     alcance, o se arranca de cero sobre la API .NET existente?
   **No retomar implementación sin luz verde explícita y fresca del
   usuario.**

## Pendiente de decisión (el usuario define alcance, no el asistente)

- **Ficha del paciente sigue incompleta**: ~~CURP~~ y ~~foto~~
  **RESUELTOS** — ambos ya se resolvían en `buscar_expediente()` pero se
  descartaban al armar `PatientMember` (`visit_queue_usecase._build_member`);
  ahora se propagan y se ven en el header del expediente (foto real,
  JPEG optimizado, en vez del ícono genérico). Sexo/tipo de sangre/
  teléfono de contacto/email/dirección **siguen sin existir en ningún
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
- **Autorización de Recetas — frontend**: backend ya completo y validado
  (ver sección arriba), falta la pantalla de cola de pendientes +
  autorizar/rechazar. Preguntar al usuario si seguir con esto antes de
  construirlo.
- **Autorización de Estudios**: segunda mitad de "Autorizadores", queda
  aparte porque falta definir el criterio de negocio (a diferencia de
  Recetas, que ya tenía `cuadro_basico`/`is_controlled` en el catálogo).
- **Catálogo `Autorizadores` (huérfano)**: sin origen claro en el legado,
  cero consumidores confirmados — el usuario todavía no decide qué hacer
  con él.
- **Licencias/Incapacidades — autorización**: mismo patrón del legado
  pendiente de revisar, prioridad baja.

## Estado del repo

**Sin commitear todavía** — todo lo de hoy (historia clínica, catálogos,
`ClinicalHistoryRevision`, `ConsultationAddendum`, fix de migración
`medicos/0009`, expediente con datos reales + selector de núcleo, portal
de citas completo, backend de Autorización de Recetas) está en el working
tree. Correr `git status` antes de seguir para confirmar el alcance
exacto antes de armar el commit.
