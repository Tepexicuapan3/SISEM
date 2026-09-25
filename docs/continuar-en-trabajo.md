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
- **`herramientas`, `movimientos`, `opciones`**: apps vacías, sin alcance
  definido.
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

**Sin commitear todavía** — todo lo de hoy (historia clínica, catálogos,
`ClinicalHistoryRevision`, `ConsultationAddendum`, fix de migración
`medicos/0009`, expediente con datos reales + selector de núcleo, portal
de citas completo, backend de Autorización de Recetas + sus 3 mejoras de
NOM-024, banner de anuncios y calendario visual del Portal de Citas) está
en el working tree. Correr `git status` antes de seguir para confirmar el
alcance exacto antes de armar el commit.
