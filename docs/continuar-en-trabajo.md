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
> legado por RBAC real), verificado contra Postgres real, más 3 mejoras
> de NOM-024/funcionalidad (segregación de funciones, historial de
> auditoría, notificación de rechazo). También se cerraron 2 de 3 mejoras
> no bloqueantes del Portal de Citas (banner de anuncios + calendario
> visual mensual reemplazando el input simple; especialidades se descartó
> por estar deprecated en el propio backend). La **migración de médicos
> desde el legado** quedó con plan acordado pero sin implementar (ver
> "Bloqueado", punto 7). La integración **EMA Recetas sigue bloqueada** —
> solo hay un plan, no se implementó nada (instrucción explícita del
> usuario), esperando que responda 3 preguntas abiertas (ver sección
> "Bloqueado"). La conexión a Postgres dev (`50.192.41.223`) estuvo
> **intermitente** en el tramo final de la sesión — algunas verificaciones
> end-to-end quedaron pendientes de confirmar, marcadas explícitamente
> abajo.

## Cómo usar este documento

1. Lee "Bloqueado" primero: son las cosas que precisamente necesitan la
   red del trabajo (acceso a Oracle/MySQL legado).
2. "Completado" es para no repetir trabajo ni re-preguntar qué ya existe.
3. "Pendiente de decisión" necesita que el usuario (no el asistente)
   defina algo antes de tocar código.

## Tablas de MySQL (legado) pendientes de migrar a Postgres — vista consolidada

Checklist rápido de qué tabla del legado ya se migró y cuál sigue pendiente
— el detalle completo de cada una vive en las secciones "Completado"/
"Bloqueado" correspondientes más abajo, esto es solo para no tener que
releer todo el documento cada vez.

### Ya migradas (no repetir trabajo)
- `his_clinica` → `consulta_medica.ClinicalHistory` (3385 historias reales,
  comando `migrar_historial_clinico_legacy.py`, ✅).
- `his_notas` → `consulta_medica.LegacyConsultationRecord` (604,178 notas,
  archivo de solo lectura, ✅).
- `det_hisnotcie` → `consulta_medica.LegacyConsultationDiagnosis` (529,315
  diagnósticos CIE-10, ✅).

### Pendientes (necesitan acceso a la red del trabajo / al dump real)
1. **`his_clinicad`** (historia clínica de ESTOMATOLOGÍA del legado) — tabla
   aparte de `his_clinica`, **sigue sin explorar**, no existe comando de
   migración todavía. **Importante, no confundir**: el comando nuevo de
   esta sesión `backend/apps/consulta_medica/management/commands/
   migrar_alergias_estructuradas.py` migra DENTRO de Postgres (de
   `ClinicalHistory.allergies`/`StomatologyHistory.allergy_*`, que ya están
   en Postgres, hacia la nueva tabla `Allergy`) — **no lee MySQL en
   absoluto**. `his_clinicad` en el legado sigue intacto, sin tocar en el
   origen.
2. **`dbclinicas.cat_medicos`** (médicos) — plan ya cerrado con el usuario
   (ver "Bloqueado", punto 7), pero el comando `migrar_medicos_legacy.py`
   **todavía no existe** y falta acceso al dump real de esa tabla. Conteos
   dados por el usuario (sin verificar contra dump): ~2730 médicos, ~560
   sin `cd_usuario` asignado.
3. **`det_cirugia`** / **`det_ambulancias`** — sin backup del legado
   todavía (ver "Bloqueado", punto 4). Los modelos ya dejan `legacy_folio`
   listo para cuando llegue el backup, así que en cuanto exista el dump el
   trabajo de mapeo/comando es rápido.
4. **`his_hospital`** (~32,000 filas) — único caso donde el modelo/infra en
   Postgres YA está 100% listo y verificado (`hospitalizacion.
  HospitalAdmission`, ver "Completado 2026-09-24"); solo falta que el
   usuario ejecute la migración de datos reales con el mapeo ya
   documentado en `docs/runbooks/his-hospital-migracion-mapeo.md`.

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

### Portal de Citas — 2 de 3 mejoras no bloqueantes cerradas
De la lista de mejoras futuras (calendario visual, anuncios,
especialidades), quedó así:
- **Calendario visual mensual — HECHO** —
  `PortalReservarCitaPage.tsx` reemplazó el `<input type="date">` por
  `<Calendar>` (`shared/ui/calendar.tsx`, `react-day-picker`), con
  navegación de mes (`onMonthChange` dispara refetch de
  `getDisponibilidadMensual`) y días pintados con/sin cupo (`modifiers`
  `disponible`/`sinCupo` a partir de `dias[]`, punto verde/rojo bajo el
  número). Días anteriores a hoy deshabilitados (`disabled={{ before }}`).
  Al cambiar de consultorio se resetea fecha + mes visible. Type-check y
  ESLint limpios. **Verificación end-to-end contra Postgres real
  PENDIENTE** — la conexión a `50.192.41.223` estuvo intermitente en este
  tramo de la sesión (se cayó varias veces a mitad de verificar); el
  contrato de `get_disponibilidad_mensual` se confirmó leyendo
  `portal_citas/views.py:372-402` y `services/slots_service.py`
  directamente (no adivinado), pero falta el click-through real en
  navegador con datos de un consultorio en línea real. Hacerlo apenas la
  red esté estable antes de dar esto 100% por cerrado.
- **Anuncios del portal — HECHO** — banner nuevo
  (`PortalAnunciosBanner.tsx`) arriba de la lista en
  `PortalMisCitasPage.tsx`, consume `GET /portal/anuncios`
  (`portalAnunciosAPI.getAll()`). Sin anuncios vigentes no renderiza nada
  (mismo criterio que el backend: nunca 404, lista vacía). Misma
  verificación E2E pendiente que el punto anterior, por el mismo motivo
  de red.
- **Especialidades del portal — DESCARTADO, no era un gap real** — el
  propio backend marca `especialidadId` como DEPRECATED en
  `SlotsPortalQuerySerializer` (`portal_citas/views.py:230-234`, "cliente
  legado", a remover una release después del portal nuevo). El flujo real
  (`PortalReservarCitaPage.tsx`) ya filtra 100% por `consultorioId` —
  agregar un selector de especialidad iría en contra de la dirección de
  arquitectura ya escrita en el código. No construir esto salvo que el
  usuario pida explícitamente revertir esa decisión.

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
7. **Migración de médicos desde el legado** (`dbclinicas.cat_medicos` →
   `medicos.CatMedico`) — plan cerrado con el usuario en esta sesión,
   **nada implementado todavía**. Conteos reales dados por el usuario (no
   verificados contra el dump, solo contra su propia consulta al legado):
   ~2730 médicos, ~560 sin `cd_usuario` asignado — de esos 560, algunos
   tienen una cuenta pero con un rol distinto al de médico, otros están
   realmente vacíos. Plan acordado:
   1. Agregar `CatMedico.legacy_no_medico` (`CharField` único, indexado —
      tarea 1.1/1.2 de `sdd/historia-clinica-migracion/tasks`, Engram
      obs #482, nunca implementada pese a estar planeada desde antes).
   2. Comando nuevo `migrar_medicos_legacy.py` (no existe todavía): por
      cada médico del legado, matchear `cd_usuario` contra
      `SyUsuario.usuario` ya migrado (el rol de esa cuenta NO bloquea el
      match — `SyUsuario.usuario == cat_usuarios.cd_usuario` sin importar
      rol) y setear `CatMedico.id_usuario`; si `cd_usuario` está vacío,
      `CatMedico.id_usuario` queda `NULL` (ya soportado por diseño,
      "médico externo") + `nombre_display` con el nombre real para que no
      aparezca como "Médico #N" en la UI.
   3. **Sentinela `SyUsuario` compartido — DESCARTADO, ya no hace falta**:
      la idea original (Engram obs #480) asumía que `VisitConsultation`
      necesitaba un doctor NOT NULL; pero las notas históricas migradas
      viven en `LegacyConsultationRecord.doctor_code_legacy`, que es
      texto plano, no FK (confirmado leyendo el modelo) — no hay
      integridad referencial que romper.
   - **No se necesita generar usuarios únicos para nadie** — decisión
     explícita del usuario, los médicos sin `cd_usuario` en el legado son
     "solo historial", no requieren login real.
   - Falta acceso al dump/tabla real de `dbclinicas.cat_medicos` para
     poder migrar de verdad — mismo bloqueo de red que el resto de esta
     sección.

## Pendiente de decisión (el usuario define alcance, no el asistente)

- **Ficha del paciente sigue incompleta**: ~~CURP~~ y foto se habían
  resuelto en `buscar_expediente()` (ya no se descartaban al armar
  `PatientMember`), pero **CURP se removió de nuevo el 2026-09-17** — ver
  sección nueva abajo, "CURP removido temporalmente (2026-09-17)". Foto
  sigue funcionando (JPEG optimizado, en vez del ícono genérico). Sexo/
  tipo de sangre/teléfono de contacto/email/dirección **siguen sin existir
  en ningún modelo** — hay que definir de dónde salen (¿sincronizar más
  campos desde Oracle? ¿capturarlos en SIRES?) antes de poder mostrarlos.
- **CURP removido temporalmente (2026-09-17)**: el commit `795c2eb`
  (12-sep-2026) había agregado `curp` a `CatEmpleado`/`CatFamiliar`
  (`backend/apps/administracion/models/`), pero la columna **nunca se creó
  en Postgres** (solo existe en el DDL `backend/storage/expedientes-ddl/002_tablas_faltantes_expediente.sql`,
  nunca aplicado) — rompía en producción TODA query sobre esos modelos sin
  `.only()` (`UndefinedColumn: column cat_empleados.curp does not exist`).
  Se sacó el campo de los modelos, del SQL crudo en
  `buscar_expediente.py` (`SQL_EMPLEADO`/`SQL_FAMILIAR`), y se ajustó
  `test_patient_lookup_api.py` para reflejar que `curp` llega en `None`
  (`_build_member` ya usaba `.get("CURP") or None`, así que no rompe nada
  downstream — frontend ya tenía fallback `?? SIN_DATO`). `makemigrations`
  no generó nada nuevo (el campo nunca había llegado a tener su propia
  migración — drift preexistente entre modelo y migración `0003`).
  **Para restaurarlo bien** (sesión futura, no trivial):
  1. Correr el DDL existente (`ALTER TABLE cat_empleados/cat_familiar ADD
     COLUMN IF NOT EXISTS curp varchar(18)`) contra Postgres.
  2. Backfill: el sync (`sync_service.py`) solo actualiza filas cuya
     `fec_ult_actualizacion` cambió, así que agregar la columna vacía NO
     la va a llenar sola para expedientes ya sincronizados — hace falta un
     backfill explícito (o forzar una resincronización completa) para
     `cat_empleados` (Oracle sí tiene CURP con datos ahí).
  3. `cat_familiar` es el caso difícil: Oracle **nunca tuvo** columna CURP
     en esa tabla, así que agregar la columna en Postgres sin más rompe el
     sync de esa tabla en cada corrida (`sync_service.py` arma el SELECT
     contra Oracle descubriendo columnas dinámicamente vía
     `information_schema.columns` de Postgres — si Postgres tiene `curp`
     y Oracle no, el SELECT a Oracle falla). Hay que decidir: ¿excluir
     `curp` del descubrimiento dinámico para `cat_familiar` específicamente,
     o resolver de otra fuente (derivarlo del titular vía RENAPO,
     capturarlo a mano en SIRES, etc.)? No hay una respuesta obvia — el
     usuario tiene que decidir antes de tocar `sync_service.py`.
- **Interoperabilidad HL7/CDA**: nunca se verificó contra el texto
  oficial del DOF si NOM-024 exige un formato de intercambio específico.
- **Segundo catálogo NOM-024**: confirmar con el certificador cuál es.
- **Fase 5 (médicos)**: cerrar la ventana de compatibilidad de IDs
  necesita telemetría real de producción (`WARNING MEDICO_ID_LEGACY_FALLBACK`).
- ~~**`herramientas`, `movimientos`, `opciones`**~~ **ELIMINADAS (2026-09-28)**: eran apps con
  todos sus archivos vacíos, fuera de `INSTALLED_APPS` (junto con `core`).
- **Farmacia**: `domain-map.md` dice "Discovery" pero en realidad YA HAY
  un módulo real (`VacInventario`, inventario de vacunas) sin frontend —
  el doc de arquitectura está desactualizado, corregirlo.
- **Cirugías/Ambulancias — mejoras futuras** (sesión anterior, siguen
  pendientes): internamiento hospitalario, calendario visual,
  autorización de ambulancias segmentada por clínica, catálogo de
  horarios de quirófano.
- Correr `python manage.py seed_catalogos_crud_permissions` a mano en el
  próximo deploy (sesión anterior, sigue pendiente).
- **Códigos de permisos huérfanos en `seed_navigation_menu` (deuda
  preexistente)**: el comando reporta 9 permisos sin consumidor bajo
  `admin:catalogos:*` (`cie9_mc`, `clasificaciones_cirugia`,
  `destinos_ambulancia`, `estudios`, `motivos_cancelacion_cirugia`,
  `motivos_traslado`, `tipos_cirugia`, `tipos_servicio_ambulancia`,
  `tipos_traslado`). Mismo origen que las fallas preexistentes de
  `menu-destinations.test.ts` ya documentadas — el usuario decidió
  dejarlo como change aparte. Sin acción requerida en esta sesión.
- ~~**Autorización de Recetas — frontend**~~ **COMPLETADO (2026-09-22)**:
  feature plana `frontend/src/features/autorizacion-recetas/` (cola Pendientes +
  Historial, autorizar/rechazar con dialogs). Backend validado, frontend +
  frontend commiteado en rama `SISEM-15-07-2026` (commit `9e9b604`), pendiente
  de push. Incluye eliminación atómica del placeholder huérfano
  `/admin/autorizacion/recetas`.
- **Autorización de Estudios**: segunda mitad de "Autorizadores", queda
  aparte porque falta definir el criterio de negocio (a diferencia de
  Recetas, que ya tenía `cuadro_basico`/`is_controlled` en el catálogo).
- **Catálogo `Autorizadores` (huérfano)**: sin origen claro en el legado,
  cero consumidores confirmados — el usuario todavía no decide qué hacer
  con él.
- **Licencias/Incapacidades — autorización**: mismo patrón del legado
  pendiente de revisar, prioridad baja.
- **Rangos CIE-10 de `SensitiveCieRange` (2026-09-28)**: los rangos
  sembrados (`B20-B24` VIH, `F10-F19` sustancias, `F00-F09`/`F20-F99` salud
  mental) son un valor por defecto razonable, no una decisión final —
  confirmar con calidad/jurídico del hospital. También falta decidir a qué
  roles se les asigna cada uno de los 3 permisos nuevos
  (`clinico:diagnosticos_vih:read`/`..._salud_mental:read`/
  `..._sustancias:read`) — ver checklist de deploy en "Completado
  2026-09-28" arriba.
- **Plazo legal de solicitudes ARCO** (Fase 4, YA implementada con
  default configurable): 20 días hábiles lunes-viernes vía
  `ARCO_PLAZO_DIAS_HABILES` — confirmar con jurídico el número y si hay que
  descontar feriados oficiales (el único punto a cambiar es
  `add_business_days` en `administracion/use_cases/arco/arco_usecase.py`).

## Completado 2026-09-17 — infraestructura (gateway, CORS/CSRF, celery-beat)

Sesión aparte, enfocada en poner a producción el acceso público a SISEM
(puerto 80/443) y al **Portal de Citas** (puerto 8081) vía la IP pública
`187.217.145.12` (servidor `sma1`, Linux, IP interna `10.15.15.22`).
Resultado: SISEM público funcionando 100%; Portal de Citas funcionando
100% por red interna, **bloqueado en público solo por falta de una regla
de red externa a este repo** (ver "Bloqueado" abajo).

1. **Typo crítico en el gateway externo — corregido y desplegado**.
   `nginx/conf.d/sisem.conf:1` (repo `ngnix-gateway`) tenía `sserver {`
   en vez de `server {`, commiteado en `main` desde antes de esta sesión.
   nginx carga todo `conf.d/*.conf` como un solo bloque: ese typo hacía
   fallar `nginx -t` completo, así que **cualquier restart del contenedor
   `proxy_nginx` tiraba abajo SISEM y Portal de Citas juntos**, no solo
   uno. Corregido, pusheado, pulleado en `sma1` y recargado con
   `nginx -s reload` (verificado: `syntax is ok` / `test is successful`).

2. **Gap de CORS/CSRF para el Portal de Citas por IP pública — corregido**.
   `DJANGO_CORS_ALLOWED_ORIGINS` y `DJANGO_CSRF_TRUSTED_ORIGINS` (`.env`
   de SIRES) tenían `https://10.15.15.22:8081` (IP interna) pero les
   faltaba `https://187.217.145.12:8081` (IP pública) — a diferencia de
   `ALLOWED_HOSTS`, estas dos variables comparan origin completo
   (scheme+host+puerto) sin normalizar puerto, así que cualquier
   POST/PUT real (login, agendar cita) desde la IP pública iba a tirar
   403 aunque la página cargara bien. Se agregó la entrada faltante a
   ambas variables y se recreó `backend`
   (`docker compose up -d --force-recreate backend`).

3. **`celery-beat` quedaba `unhealthy` permanentemente — corregido**.
   Causa real: `backend/Dockerfile` define un `HEALTHCHECK` (`curl
   localhost:5000/health`) pensado para el proceso `daphne` del servicio
   `backend`; `celery-beat` usa la misma imagen pero su `command:`
   levanta `celery -A config beat`, que no expone HTTP en el 5000 — el
   check fallaba siempre, sin relación con si el scheduler realmente
   funcionaba. `celery-worker` ya tenía este problema resuelto con un
   healthcheck propio (`celery inspect ping`); a `celery-beat` nunca se
   le agregó el equivalente. Se agregó un `healthcheck:` propio en
   `docker-compose.yml` (repo `SIRES`) que valida que
   `/data/celerybeat-schedule` se siga reescribiendo (margen de 600s,
   acorde al `beat_max_loop_interval` default de Celery sin overrides en
   este proyecto — confirmado en `config/settings.py`). Commiteado
   (`bab53ab`, "cambiso celery"), pendiente de push/deploy al momento de
   escribir esto.

## Bloqueado (2026-09-17) — necesita al equipo de red, no código

- **Portal de Citas inalcanzable en `https://187.217.145.12:8081`
  (timeout) pese a que todo lo demás ya se probó sano.** Diagnóstico
  hecho por eliminación, capa por capa, con evidencia en cada paso:
  - Docker publica el puerto bien (`docker ps` → `0.0.0.0:8081->8081/tcp`).
  - nginx del gateway sirve bien (`curl -k -I https://localhost:8081` en
    `sma1` → `200 OK`).
  - Portal de Citas responde bien por la IP interna
    (`https://10.15.15.22:8081` funciona completo).
  - Firewall del SO en `sma1` no filtra nada (`ufw` inactivo, `iptables
    -L INPUT` con policy `ACCEPT` y cero reglas).
  - Conclusión: el router/firewall perimetral que traduce
    `187.217.145.12` hacia `10.15.15.22` tiene la regla de NAT/port-forward
    para `80` y `443` (por eso SISEM sí entra) pero **le falta la regla
    para `8081`**. Nada de esto se arregla desde los repos ni desde
    `sma1` — hay que pedirle a quien administre ese equipo (Telecom/Redes
    del Metro) que agregue: **NAT/port-forward TCP 8081, de
    `187.217.145.12:8081` hacia `10.15.15.22:8081`**, mismo criterio que
    ya existe para 80/443. En cuanto se agregue esa regla, no hace falta
    tocar nada más — todo el resto de la cadena ya quedó probado.

## Completado 2026-09-23 — Dispensación de Farmacia

Flujo integral receta autorizada → descuento de stock vía kardex de almacén,
implementado y verificado contra suite con 149 tests, branch `SISEM-15-07-2026`
(commit local `dcae826`, sin pushear).

### Dispensación de Farmacia — descuento de stock en Almacén
**Qué se implementó**: puente entre la autorización de recetas (ya funcional)
y el descuento real de stock de medicamentos/insumos. Mapeo manual
`MedicamentoInsumo` (FK `medicamento` → FK `insumo`, con `factorConversion`)
permite que una receta autorizada de un medicamento específico descuente
unidades del insumo correspondiente en el Almacén tipo FARMACIA, vía la
kardex existente de entrada/salida de existencias.
- Modelo nuevo: `farmacia.MedicamentoInsumoMap` (FK medicamento + FK insumo +
  factor de conversión, único por medicamento).
- Modelo nuevo: `farmacia.PrescriptionDispensation` (FK receta + actor +
  cantidad dispensada, con auditoria de cambios via historial).
- Endpoint nuevo: `POST /api/v1/prescriptions/<id>/dispense` (valida
  autorización, mapeo medicamento↔insumo, stock disponible, previene
  doble-dispensación via `select_for_update` en la transacción).
- Gate de autorización: respeta la decisión del autorizador ya tomada
  (`PrescriptionAuthorization.estatus = AUTHORIZED`), **nunca toca ese
  módulo** — segregación limpia.
- **149 tests, todos pasan** — incluye casos de borde (stock insuficiente,
  medicamento sin mapeo, doble dispensación concurrente, rollback por error).
- Commit `dcae826` local, branch `SISEM-15-07-2026`.

### Verificación manual pendiente (Postgres real, DEV)

**Paso 1 — Preparar datos reales**
```bash
python manage.py seed_farmacia_almacenes
```
Cargar al menos un mapeo vía `POST /api/v1/almacen/medicamento-insumos`
(`{"medicamento": <id>, "insumo": <id>, "factorConversion": 1}`) y stock
real en ese insumo (una "entrada" normal en Almacén de Insumos, almacén
tipo FARMACIA).

**Paso 2 — Confirmar que NO toca la columna jsonb**
```python
# python manage.py shell
from django.conf import settings
settings.DEBUG = True
from django.db import connection, reset_queries
reset_queries()

from apps.consulta_medica.uses_case.prescription_dispensation_usecase import dispense
dispense(prescription_id=<id_receta_real>, items=[...], actor_id=<user_id>)

sospechosas = [q["sql"] for q in connection.queries if '"items"' in q["sql"]]
print(f"{len(connection.queries)} queries totales; sospechosas (deben ser 0): {sospechosas}")
```

**Paso 3 — Confirmar que la concurrencia no duplica el descuento**
```bash
curl -X POST http://localhost:5000/api/v1/prescriptions/<id>/dispense \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"items":[{"prescriptionItemId": <id>, "quantity": <n>}]}' &
curl -X POST http://localhost:5000/api/v1/prescriptions/<id>/dispense \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"items":[{"prescriptionItemId": <id>, "quantity": <n>}]}' &
wait
```
Esperado: una responde 200, la otra 409 (`ALREADY_DISPENSED` o
`DISPENSATION_EXCEEDS_PRESCRIBED`). La existencia/kardex del insumo debe
reflejar UNA sola dispensación, no dos.

**Paso 4 — Rollback por stock insuficiente**
Dispensar más cantidad de la disponible. Esperado: 409 `INSUFFICIENT_STOCK`,
sin ningún campo modificado (ni el item de receta, ni la existencia).

**Solo después de correr esto y confirmar los 4 pasos, hacer `git push` del
commit `dcae826` y cerrar el change con `sdd-archive`.**

## Completado 2026-09-24 — Hospitalización (NOM-024)

Change `his-hospital-modelo-nom024` implementado y verificado (17/17 tasks,
PASS sin CRITICALs). Modelos nuevos `HospitalAdmission` y `HospitalAdmissionRevision`
(app `hospitalizacion`) con protección NOM-024 (snapshot de revisión, append-only
real, soft-delete), más 2 catálogos nuevos (`CatTipoHospitalizacion`,
`CatTipoAlta`) con 23+6 valores extraídos y verificados contra el dump real.
Campo puente `legacy_cd_clinica` agregado a `CatCentroAtencion` para facilitar
la migración de datos reales desde el legado.

**Estado**: modelo e infraestructura **100% implementados y verificados** (commit
`e66328b`); **PENDIENTE migración de datos reales** (~32,000 filas de
`his_hospital` del legado — el usuario ejecutará usando el documento de mapeo
ya generado: `docs/runbooks/his-hospital-migracion-mapeo.md`).

**También pendiente**: ~300 médicos sin usuario asignado (`medicos-legacy-field-bulk-import`,
mismo commit `e66328b`). El usuario está pensando el rediseño de idempotencia
del comando migración — **no relajar la validación de `id_usuario` sin
resolver ese aspecto**.

## Completado 2026-09-25 — `menu-destinations-drift-cleanup`

Causa raíz: dos comandos de seed de permisos separados corrían independientemente
—`seed_navigation_permissions` en `start-docker.sh` + `seed_catalogos_crud_permissions`
sin ejecutarse nunca en ese script—, dejando 8 permisos de catálogos sin sembrarse
en producción.

**Fix aplicado**:
- Agregado `seed_catalogos_crud_permissions` a `start-docker.sh` (solo si no existen,
  idempotente).
- Agregadas ~17 labels faltantes a `menu-destinations.labels.ts` (códigos de permisos
  que el frontend esperaba pero no existían).
- Eliminado label huérfano `/admin/reportes` y nodo muerto `administracion.catalogos.estudios`
  de `navigation_seed.py` (no tenían consumidor real).

**Resultado**: `seed_navigation_menu` ahora reporta **0 códigos huérfanos** (antes 9);
`menu-destinations.test.ts` **3/3 OK**. **Estado**: implementado y verificado,
pendiente de commit por el usuario.

## Completado 2026-09-25 — Fix migración `catalogos.0016`

**Bug**: en una base de datos completamente fresca (sin historial migración previo),
`0016_autorizadores_fk_integrity.py` fallaba por constraint FK duplicada. Causa:
`0013_create_missing_catalog_tables.py` usaba el registro de apps global en vez
del histórico, creando la constraint dos veces.

**Fix aplicado**: migración reescrita con `SeparateDatabaseAndState` + verificación
de introspección antes de crear la constraint (mismo patrón defensive que `0015`).

**Nota de alcance acotado**: `consulta_medica.0012` tiene un problema similar sospechado
pero NO confirmado (posible artefacto de volumen Docker reciclado, no reproducido
limpio) — queda para otra sesión, requiere reproducir en un entorno 100% limpio.

**Estado**: implementado, verificado solo en SQLite (no se pudo confirmar contra
Postgres real por regla de no tocar bases externas/DEV). El usuario tiene el comando
(`python manage.py migrate catalogos`) para confirmarlo cuando prepare su propia
Postgres de prueba.

## Completado 2026-09-25 — `incapacidad-medica-recepcion-frontend`

**Hallazgo clave**: el backend y la mayoría del frontend YA existían (emisión desde
consulta médica, historial por paciente, reporte con export). Solo faltaba la
pantalla de Recepción.

**Decisión de alcance** (confirmada con evidencia del legado java-main: 6 pantallas
de admisión distintas enlazaban solo al historial de solo lectura, nunca a captura):
la pantalla de Recepción es SOLO CONSULTA/HISTORIAL, sin formulario de creación —
la creación sigue siendo exclusiva del médico.

**Cambio de backend**: permiso nuevo `recepcion:incapacidad:read` (reemplaza el
permiso fantasma `recepcion:incapacidad:create` que nunca existió en RBAC real),
usado SOLO en el GET de historial — el POST de creación sigue exigiendo rol médico
exclusivamente. Verificado con test adversarial: mismo usuario, GET 200 y POST 403.

**⚠️ ACCIÓN REQUERIDA EN DEPLOY**: después de correr `seed_navigation_permissions`
en el servidor, hay que asignar manualmente `recepcion:incapacidad:read` al rol de
Recepción — si no, la pantalla queda invisible para el personal real aunque el código
esté bien.

**Estado**: implementado y verificado (PASS sin hallazgos), pendiente de commit por
el usuario.

## Completado 2026-09-28 — Alergias unificadas + diagnósticos sensibles (NOM-024) + fix deuda técnica `apps.catalogos`

Punto de partida: se revisó un documento externo (propuesta de terceros) que
sugería rehacer la historia clínica de SISEM. Al contrastarlo contra el
código real se confirmó que la mayor parte ya existía (`ClinicalHistory`
unificada, versionado, odontograma FDI); quedaban 2 brechas reales que sí se
implementaron, más deuda técnica preexistente que apareció en el camino.

### Fase 1 — Alergias normalizadas
`ClinicalHistory.allergies` (texto libre) y las 6 columnas
`StomatologyHistory.allergy_*` quedaban duplicadas y sin cruzar contra
medicamentos — una alergia capturada en Estomatología no aparecía en
Medicina General. Reemplazadas por:
- Modelo `consulta_medica.Allergy` (1:N por paciente, categoría/severidad/
  sustancia/reacción) + `AllergyRevision` (versionado NOM-024, migración
  `0026`). Visible desde ambas especialidades siempre.
- `StomatologyHistory` ahora versiona ediciones (`StomatologyHistoryRevision`)
  — cerraba una brecha real, era el único modelo de historia clínica sin
  snapshot-antes-de-sobreescribir.
- Comando `migrar_alergias_estructuradas.py` (dry-run + idempotente) migra
  el texto libre YA EXISTENTE EN POSTGRES hacia `Allergy` — **ojo, esto NO
  toca MySQL** (ver sección de tablas pendientes arriba, `his_clinicad`
  sigue sin migrar del legado).
- Cruce receta↔alergia en `add_prescription_item`: si el medicamento choca
  con una alergia activa, se devuelve una advertencia y el frontend debe
  reenviar con `acknowledgeAllergyWarning: true` para continuar — decisión
  del usuario, advertencia con constancia auditada, nunca bloqueo duro.
- Frontend: componente `AllergyList.tsx` reemplaza el textarea/6 campos en
  Generales y Estomatología; la tarjeta "Alertas Médicas" del expediente
  (que tenía `alergias: []` hardcodeado) ya muestra datos reales.

### Fase 2 — Diagnósticos sensibles (VIH / salud mental / sustancias)
No existía ningún control de acceso para diagnósticos CIE-10 sensibles.
- Catálogo `catalogos.SensitiveCieRange` (migración `0030`, seed inicial
  `B20-B24`→VIH, `F10-F19`→sustancias, `F00-F09`/`F20-F99`→salud mental —
  **rangos por defecto, pendientes de confirmar con calidad/jurídico**, ver
  "Pendiente de decisión" abajo).
- Servicio `classify_cie()`: compara solo el PREFIJO DE CATEGORÍA de 3
  caracteres (no el código completo) — se encontró y corrigió un bug real
  de diseño: comparar el código completo como string rompía con subcódigos
  decimales (`"B24.9" > "B24"` lexicográficamente, quedaba fuera del rango
  aunque clínicamente sí es VIH).
- Cuando el usuario no tiene el permiso requerido, se redacta el
  diagnóstico (`cieCode`/`cieDescription` Y el texto ligado como
  `primaryDiagnosis`/`notes` — dejar el texto libre visible hubiera hecho
  trivial esquivar la redacción) — el resto de la consulta se sirve normal,
  decisión del usuario de no ocultar el registro completo. Aplicado en
  historial de consultas y diagnósticos secundarios. Evento de auditoría
  `SensitiveDiagnosisRedacted` (uno por request, no bloqueante).
- 3 permisos nuevos sembrados: `clinico:diagnosticos_vih:read`,
  `clinico:diagnosticos_salud_mental:read`,
  `clinico:diagnosticos_sustancias:read`. **⚠️ ACCIÓN REQUERIDA EN DEPLOY**
  (mismo patrón que `recepcion:incapacidad:read` en la sesión del 25-sep):
  después de correr `seed_navigation_permissions`, ningún rol tiene estos 3
  permisos asignados todavía — hasta que se asignen a mano, **todo el
  personal, incluidos médicos, va a ver "Diagnóstico restringido"** para
  VIH/salud mental/sustancias. Es el comportamiento seguro por defecto,
  pero avisar antes de que el personal clínico lo note y genere tickets.

### Deuda técnica preexistente en `apps.catalogos` — encontrada y corregida
Al escribir tests nuevos para la Fase 2 aparecieron **45 tests
preexistentes rotos** en `apps.catalogos`, sin relación con este trabajo
(confirmado con `git stash`: fallaban igual contra el código limpio). Causas
reales, cada una verificada contra el modelo/vista/serializer actual (no
supuestas):
- `CatCentroAtencion.schedule` ya no existe (reemplazado hace tiempo por el
  modelo `CatCentroAtencionHorario`) y `Consultorios.code` se renombró a
  `numero` — los tests seguían usando los nombres viejos.
- A todas las URLs de los tests de catálogos les faltaba la barra final que
  las rutas reales exigen (`care-centers/`, `areas/`, `consulting-rooms/`).
- Tests que hacen login real sin `cache.clear()` en `setUp` — el
  policy_store (bloqueo de "sesión activa" por `user_id`) vive en cache
  (Redis), no en la base de datos, así que sobrevive al rollback de
  transacción entre tests; con SQLite reutilizando el mismo `id_usuario`
  autoincremental tras cada rollback, el 2º test en adelante chocaba con la
  sesión activa que dejó el 1º (mismo patrón ya usado en
  `apps.authentication.tests.test_auth_api.py`, solo faltaba copiarlo acá).
- Códigos de error desactualizados en los asserts (`PERMISSION_DENIED` →
  `INSUFFICIENT_PERMISSIONS`/`CSRF_INVALID`, la API real cambió de códigos
  y los tests no se actualizaron).
- `HasCatalogPermission.__init__` pasó de aceptar `action`/`catalog`
  opcionales a exigirlos como posicionales — un test que probaba "qué pasa
  sin action/catalog" ya no aplica (Python lo impide al instanciar).
- `_build_user_ref`/`_build_catalog_ref` dejaron de ser métodos de
  instancia de `CatalogDetailSerializer`, ahora son funciones de módulo
  (`build_user_ref`/`build_catalog_ref`) reusadas fuera de serializers.
- `test_postal_code_service.py`: import sin el prefijo `apps.` (rompía en
  cualquier entorno, no solo Windows), ruta `/tmp/...` hardcodeada (sí
  rompía específicamente en Windows), y `CodigoPostalService.search()` es
  un `@staticmethod` que usa un singleton de MÓDULO — el test intentaba
  inyectar un repositorio de prueba en una instancia, sin ningún efecto
  real (silenciosamente consultaba el catálogo real de 15 MB).

**Efecto colateral de esta sesión**: Redis no estaba corriendo en esta PC de
desarrollo (Windows, sin Docker por decisión explícita del usuario — acá se
levanta backend/frontend por separado en bash, Docker solo se usa en
producción). Se usó el `redis-server.exe` nativo ya instalado en
`C:\Program Files\Redis\` (puerto 6379) — **no queda como servicio
persistente, hay que volver a levantarlo a mano si se reinicia la máquina**.
`CACHE_REDIS_URL`/el policy_store lo necesitan para funcionar (login,
throttling, sesión activa).

**Resultado**: 157 tests backend (consulta_medica + catalogos nuevos) +
109/109 de `apps.catalogos` completo pasan (antes: 45 fallando). `tsc
--noEmit` y `makemigrations --check` limpios.

**Estado del commit**: todo lo de arriba quedó en un solo commit
(`69297792`, "Alergias unificadas y redaccion de diagnosticos sensibles
(NOM-024)") en la rama `SISEM-15-07-2026` — **pendiente de push** (el
usuario decide cuándo).

### Checklist para cuando se despliegue este commit
1. `python manage.py migrate` (nuevas: `consulta_medica.0026`,
   `catalogos.0030`).
2. `python manage.py seed_navigation_permissions` (siembra los 3 permisos
   nuevos de diagnósticos sensibles — se ejecuta solo en `runserver`/
   `start-docker.sh`, correrlo a mano si el deploy no pasa por ahí).
3. **Asignar los 3 permisos nuevos a los roles que correspondan** (ver
   "⚠️ ACCIÓN REQUERIDA EN DEPLOY" arriba) — decisión institucional, no
   técnica.
4. Opcional pero recomendado: `python manage.py migrar_alergias_estructuradas
   --dry-run` primero, revisar el reporte, después correrlo real para
   migrar el texto libre de alergias ya existente en Postgres.
5. Rebuild del frontend (`pnpm run build` o equivalente) — se tocaron
   varios `.ts`/`.tsx`.
6. Confirmar que Redis esté corriendo donde corra el backend (ya resuelto
   en el `docker-compose.yml` de producción).

## Completado 2026-09-28 (2ª sesión) — Fases 3 y 4: bitácora de acceso + solicitudes ARCO

El plan original (`bubbly-launching-sparkle.md`) quedó en la otra PC; ambas
fases se reconstruyeron desde el código real. **Sin commitear** al momento
de escribir esto.

### Fase 3 — Bitácora de acceso al expediente
- `consulta_medica/services/record_access_audit_service.py`: evento
  `PatientRecordAccessed` (`recurso_tipo="expediente"`, `meta` con
  `noExp`/`pkNum`/`section`) en los **8 GET del expediente** (historia
  clínica, estomatología, alergias, consultas, consultas legado,
  odontograma, incapacidades, estudios) — no solo los 2 del plan original.
- **Deduplicación** con `cache.add` (Redis): máximo 1 evento por
  (actor, no_exp, pk_num, sección) cada 5 min — sin esto, los refetch de
  TanStack Query al reenfocar la ventana generaban decenas de filas por
  lectura. Si Redis no responde, se registra igual (mejor duplicar que
  perder un acceso). Nunca bloquea la lectura (`raise_on_error=False`).
- `GET /api/v1/bitacora-acceso` (`administracion/views/access_log_views.py`
  + `repositories/access_log_repository.py`): lista `PatientRecordAccessed`
  + `SensitiveDiagnosisRedacted` (Fase 2), filtros `tipo`/`seccion`/`noExp`/
  `pkNum`/`usuario`/`fechaInicio`/`fechaFin`, paginado. Permiso nuevo
  **`admin:auditoria:accesos:read`**.
- Frontend: `/admin/bitacora-acceso` (`features/admin/modules/bitacora-acceso/`).

### Fase 4 — Solicitudes ARCO
- Modelo `administracion.SolicitudArco` (migración `administracion.0007`):
  paciente como `no_exp`/`pk_num` planos, sin FK (`CatEmpleado` vive en la
  base `expedientes`). Folio `ARCO-AAAA-NNNNNN`.
- Plazo: `settings.ARCO_PLAZO_DIAS_HABILES` (env, default **20 días
  hábiles**, lunes a viernes, sin feriados) — **sigue pendiente de confirmar
  con jurídico**, pero ya no bloquea: se cambia por variable de entorno sin
  tocar código. `fecha_limite` se fija al recibir y no se recalcula.
- Estatus `recibida → en_proceso → procedente|improcedente` (también
  `recibida → resolución` directo). Resolver exige respuesta; **resuelta =
  inmutable** (409 `ARCO_ALREADY_RESOLVED`). Cada alta/cambio audita
  `ArcoRequestCreated`/`ArcoRequestStatusChanged` en modo ESTRICTO (si falla
  la auditoría, se revierte todo).
- Endpoints: `GET/POST /api/v1/solicitudes-arco`, `GET .../<id>`,
  `POST .../<id>/status`. Permisos nuevos **`admin:arco:read`** /
  **`admin:arco:write`** (separados a propósito).
- Frontend: `/admin/solicitudes-arco` (listado con filtro "Solo vencidas",
  alta y cambio de estatus).

### Verificación
- Backend: `apps.consulta_medica` + `apps.administracion` + `apps.catalogos`
  → 543 tests OK antes de ARCO; `apps.administracion` → 287 OK después.
  `makemigrations --check` limpio.
- Frontend: `typecheck:app` limpio, ESLint sin warnings en lo nuevo, tests de
  navegación 23/23. `menu-destinations.generated.ts` regenerado con
  `pnpm run gen:menu-destinations`.

### CURP y sexo en la ficha del paciente + limpieza de alergias (paso 1)
- **Decisión**: la "ficha del paciente" (`PACIENTE` del documento de reforma
  de historia clínica) en SIRES ES `cns_clinical_history` (ya tenía
  ocupación/escolaridad/estado civil/religión/residencia/teléfono). Ahí se
  agregaron `curp` (validación RENAPO, normalizada a mayúsculas) y `sexo`
  (`H`/`M`/`X`), migración `consulta_medica.0027` (4 `AddField` nullable).
  **NO se tocó `cat_empleados`/`cat_familiar`** (incidente 2026-09-17).
  Versionados en `ClinicalHistoryRevision` (`curp_anterior`/`sexo_anterior`)
  y auditados en `ClinicalHistoryUpdated`.
- Frontend: sección "Identificación" en el tab Generales; el header del
  expediente muestra CURP/sexo/teléfono reales (antes "No disponible").
- Bug corregido de paso: el serializer limitaba `phone` a 15 caracteres
  (modelo: 50) → editar la historia de un paciente migrado daba 422.
- Alergias texto libre, paso 1: `ClinicalHistory.allergies` salió de la API
  (serializer/contrato/tipos) y `migrar_historial_clinico_legacy` ahora
  importa `ds_alergias` directo a `cns_allergy`. **Paso 2 HECHO** en la
  historia clínica unificada (abajo): la migración `consulta_medica.0029`
  mueve el texto a `cns_allergy` y `0030` borra las columnas.
- Tests: 530 backend (`consulta_medica`/`administracion`/`recepcion`) con 10
  fallas en `test_checkin_manual_api.py`, confirmadas idénticas en `HEAD`
  limpio (worktree). Vitest: 13 fallas en 6 archivos, confirmadas idénticas
  con `git stash -u` — ninguna relacionada.
- Brechas vs. documento de reforma: **cerradas** en la sección siguiente.

### Historia clínica unificada — implementación completa del documento de reforma (2026-09-28)

Implementado el modelo del documento "Historia Clínica Unificada"
(artifact `XMxgUTzoxU6mdPMgr2xDDN`, 25-sep-2026) completo, quitando lo que
el modelo nuevo reemplaza. **Sin commitear.**

| Documento | SIRES |
|---|---|
| PACIENTE / HISTORIA_CLINICA | `cns_paciente` (ficha + CURP/sexo) y `cns_clinical_history` (cabecera: fecha/clínica/médico de apertura) — ver "Núcleo del paciente" |
| ALERGIA (estado A/R/E) | `cns_allergy` + `estado`/`motivo_estado`; resuelta = visible pero NO alerta en receta |
| ANTECEDENTE_PERSONAL / _FAMILIAR / _QUIRURGICO, HABITO | `cns_antecedente_personal`/`_familiar`/`_quirurgico`, `cns_habito` (baja lógica con motivo, CIE sensible redactado) |
| NOTA_HISTORICA | `cns_nota_historica` (solo lectura; texto acumulado partido por `[dd/mm/aaaa (usuario)]`) |
| EXPLORACION_FISICA | `cns_exploracion_fisica` por consulta (solo editable `en_consulta`) |
| SIGNOS_VITALES | ya existía (`smt_visit_vitals`); del legado → nota histórica (SIRES liga signos a visita) |
| HC_ESTOMATOLOGIA | `cns_stomatology_history` reestructurada (higiene, cepillados, hilo, tejidos blandos, ATM) |
| ODONTOGRAMA / _PIEZA | `cns_odontograma` versionado por consulta + CPOD, `cns_odontograma_pieza` con caras |
| TRATAMIENTO_DENTAL | `cns_tratamiento_dental` |
| cat_habito / cat_region_corporal / cat_estado_pieza / cat_pieza_dental | `catalogos.0031/0032` (sembrados; 52 piezas FDI) |
| SOLICITUD_ARCO.folio_unidad_transparencia | `administracion.0008` |

**Eliminado** (con los datos migrados ANTES en `consulta_medica.0029`, probado
con migración real 0028→0030 en test): los 12 textos de `cns_clinical_history`
(antecedentes, padecimiento, aparatos y sistemas, 6 exploraciones, manejo x2,
alergias), las casillas/textos/`alergia_*` de `cns_stomatology_history`,
`OdontogramTooth` (`cns_odontogram_tooth`), las `previous_*` de esos campos en
las tablas de revisión (su contenido quedó como nota histórica "versión
anterior"), el comando `migrar_alergias_estructuradas` (lo reemplaza 0029) y
en el frontend el hook/endpoint de "desactivar alergia" (ahora estado con motivo).

**Legado**: `migrar_historial_clinico_legacy` reescrito (notas históricas,
alergias por elemento, signos) y NUEVO `migrar_historia_estomatologia_legacy`
para `his_clinicad` (~24,100; respeta la inversión del sufijo `p`). Ambos
idempotentes (`legacy_ref`), con `--dry-run`. Las respuestas "NEGADAS/NIEGA/
NINGUNA" NO se convierten en alergias (se conservan como nota).

**Frontend**: tab Generales (identidad + sociodemográficos + alergias +
antecedentes + notas históricas), tab Estomatología (exploración bucal,
tratamientos, antecedentes compartidos), Odontograma (versiones, CPOD,
caras, estados desde catálogo), botón "Exploración física" en la consulta,
alergias con resolver/reactivar/error con motivo, folio UT en ARCO.

**Pendiente de validar por el área médica** (valores por defecto sembrados):
equivalencias CIE-10 de las casillas (E14, C80, I10, I95, J45, B19, B24), el
catálogo `cat_estado_pieza` y su componente CPOD (estomatología), y si la
historia sigue siendo obligatoria por especialidad (`ope_param`).

### Núcleo del paciente TAL CUAL el documento (5.1) — 2026-09-28
Pedido explícito del usuario: la sección "Núcleo del paciente: datos
permanentes" exacta y funcional (el resto del documento queda adaptado a lo
que ya existía). Estructura exacta, con la convención de nombres/auditoría de
SIRES (`usr_alta`/`fch_alta`/`est_activo`, prefijo `cns_`).

| Documento | SIRES |
|---|---|
| PACIENTE (no_exp, tp_paciente, cd_ocupacion, cd_escolaridad, cd_edocivil, cd_religion, cd_residencia, ds_telefono) | `cns_paciente` (+ curp, sexo) y `cns_paciente_revision` (versionado NOM-024) |
| HISTORIA_CLINICA (id_historia, fe_apertura, cd_clinica_apertura, cd_medico_apertura) 1:1 con PACIENTE | `cns_clinical_history` reducida a cabecera + `fe_apertura` + FK `id_paciente` |
| ALERGIA.cd_tipo_alergia → CAT_TIPO_ALERGIA (1,2,3,4,5,9) | `cat_tipo_alergia` (PK = código del documento) + FK |
| ALERGIA.severidad L/M/G, estado A/R/E, `ix_alergia_paciente` | códigos exactos, `char(1)`, índice creado |
| ANTECEDENTE_PERSONAL.estado A/R, HABITO.estado A/E | códigos exactos |
| NOTA_HISTORICA.id_historia (FK), origen M | FK obligatoria a `cns_clinical_history`; origen M (y V = versión anterior) |

- Migraciones: `catalogos.0033` (catálogo sembrado), `consulta_medica.0031`
  (esquema), `0032` (datos: ficha → paciente, revisiones, FK de notas, tipos y
  códigos), `0033` (limpieza). La 0032 está probada con migración real en test.
- API: `GET/PATCH /patients/<no_exp>/profile` (PACIENTE, evento de auditoría
  `PatientProfileUpdated`); `GET /patients/<no_exp>/clinical-history` ahora
  devuelve solo la cabecera (sin PATCH). Alergias: `allergyTypeId`,
  severidad L/M/G, estado A/R/E. `/clinical-catalogs` incluye `allergyTypes`.
- La advertencia de alergia al recetar manda severidad L/M/G.

### Limpieza de código huérfano y BD (2026-09-28)
- **Backend eliminado**: apps `herramientas`, `movimientos`, `opciones` (100%
  archivos vacíos) y `core` (fuera de `INSTALLED_APPS`, nunca corría);
  `administracion/repositories/expediente_repository.py`,
  `serializers/common_serializers.py`, `serializers/expediente_serializer.py`
  (sin ninguna referencia); comando `migrar_alergias_estructuradas` y
  `AllergyRepository.import_free_text`. Campo `curp` del contrato de
  `/visits/patient-lookup` (siempre `None`): el CURP vive en la ficha.
- **Frontend eliminado** (detectado con un análisis de imports que resuelve
  alias; ningún archivo lo importaba, incluidas cascadas): 34 archivos, entre
  ellos `GenericCatalogPage` + `catalog-definitions` + `useCatalogList` +
  `generic-catalog.api/types`, 12 `*.transform.ts` de catálogos,
  `VisitTimelinePanel` + `VisitStageNavigator` (y su test), `PdfPreviewModal`,
  `use-toast` (reemplazado por sonner), `accordion`, `__component-showcase`,
  `utils/identity/*`, `utils/web/cookies`, `useCalidadLaboralList` duplicado.
- **Se conservan a propósito** (solo los usan tests): `realtime/client.ts`,
  `realtime/protocol.ts`, `realtime/visits/protocol.ts` (shims de compatibilidad
  que re-exportan `realtime/core`/`streams`), `useRefreshSession`,
  `deriveModuleKey` (lógica de dominio probada, sin pantalla aún).
- **DDL** `storage/expedientes-ddl/002_*.sql`: quitada la columna `curp` de
  `cat_empleados`/`cat_familiar`/`cat_empleados_sis`/`cat_familiar2` (se
  recreaba en cada volumen nuevo y rompe el sync con Oracle).
- **BD**: runbook `docs/runbooks/limpieza-bd-huerfanos-2026-09-28.sql`
  (diagnóstico de solo lectura + DROP comentados). NO se ejecutó nada contra
  ninguna base.
- **Deuda detectada, no tocada** (no es código huérfano): `ExpedientesListPage`
  (ruta `/clinico/expedientes`) muestra 4 pacientes MOCK hardcodeados; 8
  errores ESLint preexistentes de reglas React 19 (`set-state-in-effect`,
  `purity`, `only-export-components`) en auth, comunicados, farmacia y recepción.

### Cierre del documento en SIRES (2026-09-29) — lo que faltaba
Alcance: solo SIRES (SISEM Java/JSP descartado por decisión del usuario).
- **Bitácora de acceso propia** (`bitacora_acceso`, `administracion.0010`) y
  **perfiles de acceso a diagnósticos sensibles** (`cat_perfil_acceso_sensible`,
  `catalogos.0035`; comando `perfil_acceso_sensible --listar/--agregar/--quitar`).
- **his_notas ampliada** (`consulta_medica.0037`): `cns_visit_consultation`
  gana `ds_padecimiento`, `ds_aparatos_sistemas`, `ds_plan_diagnostico`,
  `ds_plan_terapeutico` (+ `*_anterior` en la revisión). API camelCase
  `currentIllness/systemsReview/diagnosticPlan/therapeuticPlan` en guardar
  diagnóstico y cerrar consulta (opcionales, vacío → NULL; un error de tipeo en
  el nombre del argumento del caso de uso lanza `TypeError`). Formulario del
  médico con 4 textareas.
- **Signos vitales legado** (`cns_signos_vitales_legado`, `0038` + datos `0039`):
  numéricos "sin consulta, fecha desconocida", con rangos de plausibilidad
  (el dump tiene miles de `0`/`.` de relleno, talla en m y cm, TA con `//`);
  `ds_texto_original` guarda siempre lo capturado. NO se usa `smt_visit_vitals`
  (exige visita y peso/talla/IMC; nunca alimenta el caché de últimos signos).
  `0039` convierte las notas "signos_vitales" que ya hubiera creado el
  importador (reversible). Se ven en "Notas históricas" del expediente.
- **Plan de migración (sección 8)** (`0040`):
  - `cns_bitacora_migracion`: cada corrida de `migrar_historial_clinico_legacy`
    y `migrar_historia_estomatologia_legacy` (también `--dry-run`, y las que
    fallan). Nuevo argumento `--operador` (default: usuario del SO). La
    contraseña nunca se guarda en `opciones`.
  - `cns_conflicto_migracion` + `cns_paciente_origen_legado`: regla de la ficha
    — el legado vacío nunca borra; lo editado en SIRES nunca se pisa; entre
    filas del legado gana el `fe_hisclin` más reciente (independiente del orden
    de los comandos); toda discrepancia queda registrada. **Bug corregido**: el
    comando de his_clinica hacía `update()` ciego y al re-correrlo pisaba (o
    ponía en NULL) lo editado en SIRES.
  - **Bug corregido**: 26 pacientes con más de una fila en his_clinicad
    duplicaban antecedentes/hábitos/quirúrgicos; el importador ahora deduplica
    por paciente + contenido (incluye lo dado de baja: el legado no lo revive).
  - Runbook `docs/runbooks/migracion-historia-clinica-legacy.sql`: limpieza
    previa en MySQL (duplicados, tp_paciente inválido, códigos huérfanos,
    vista previa de conflictos, relleno de signos) y revisión en Postgres.
    Medido en el dump: 389 conflictos de ocupación y 335 de estado civil.
- Runbook de huérfanos actualizado con las 6 tablas nuevas.

### Checklist de deploy (historia clínica unificada) — ORDEN IMPORTANTE
1. **Respaldo completo de la BD de SIRES antes de migrar**: `consulta_medica.0030`,
   `0033` y `0036` borran columnas (su contenido ya se movió en la migración de
   datos previa, probado, pero un respaldo es obligatorio antes de cualquier
   migración destructiva).
2. `python manage.py migrate` (nuevas: `catalogos.0031–0035`,
   `consulta_medica.0027–0040`, `administracion.0007–0010`). Las migraciones de
   datos corren dentro de la transacción: o se aplica todo o nada.
3. Revisar el resultado: `SELECT apartado, COUNT(*) FROM cns_nota_historica GROUP BY 1;`
   y `SELECT COUNT(*) FROM cns_odontograma;` (debe haber una versión "migrated"
   por paciente que tenía odontograma).
4. Legado (en ventana de mantenimiento): seguir
   `docs/runbooks/migracion-historia-clinica-legacy.sql` — Parte A en MySQL,
   luego `migrar_historial_clinico_legacy` y `migrar_historia_estomatologia_legacy`
   con `--dry-run --operador <usuario>` primero, después reales, y Parte B.
5. `perfil_acceso_sensible --agregar ...` según lo que defina el área médica
   con datos personales (sin eso, nadie ve sin redacción los diagnósticos
   sensibles salvo por permiso).
6. Rebuild del frontend.

### Checklist de deploy (Fases 3 y 4)
1. `python manage.py migrate` (nuevas: `administracion.0007`,
   `consulta_medica.0027`).
2. `python manage.py seed_navigation_permissions` y `seed_navigation_menu`
   (3 permisos + 2 entradas de menú nuevas).
3. Asignar `admin:auditoria:accesos:read` al rol de calidad/auditoría, y
   `admin:arco:read`/`admin:arco:write` al área de compliance — sin eso, las
   2 pantallas quedan invisibles.
4. Opcional: `ARCO_PLAZO_DIAS_HABILES` en `.env` si jurídico define otro plazo.
5. Rebuild del frontend.

## Convenciones y Reglas Operacionales

### Regla: nunca probar directo contra bases de datos externas/legado

Cuando el trabajo involucra bases de datos externas (MySQL legado, Oracle, o
cualquier servidor fuera del entorno de desarrollo local) o la Postgres de
PRODUCCIÓN de SIRES, **NUNCA correr pruebas/queries directas contra esos
servidores reales desde el flujo de agentes** — ni siquiera lecturas exploratorias.

- Toda exploración de esquema/datos legado se hace contra el dump local ya
  descargado (`Dump20260903.sql`), nunca contra una conexión viva al servidor
  MySQL/Oracle real.
- Los management commands que sí requieren conexión viva (`migrar_*_legacy.py`
  con credenciales `LEGACY_MYSQL_*`) se documentan y se entregan al usuario,
  pero no se ejecutan de forma autónoma para "probar que funcionan" — la
  ejecución real la hace el usuario, bajo su propio criterio y ventana de
  mantenimiento.
- Cualquier verificación que implique escritura contra Postgres de
  producción/DEV real debe quedar documentada como checklist para que el usuario
  la ejecute él mismo (ver el checklist de verificación manual de
  `dispensacion-farmacia` como ejemplo del formato esperado).

## Estado del repo

**Actualizado 2026-09-28**: verificado con `git log origin/SISEM-15-07-2026..HEAD`
— el ÚNICO commit pendiente de push es `69297792` ("Alergias unificadas y
redaccion de diagnosticos sensibles (NOM-024)"), contiene todo lo de la
sección "Completado 2026-09-28" de arriba (Fases 1 y 2, más el fix de deuda
técnica de `apps.catalogos`). Los commits de sesiones anteriores que en su
momento se anotaron aquí como "pendiente de push" (`9e9b604`, `dcae826`,
`e66328b`, `bab53ab`) **ya están pusheados** — esa nota había quedado
desactualizada en este documento, corregida ahora. Working tree limpio al
momento de escribir esto; correr `git status` igual antes de seguir por si
hay cambios nuevos.
