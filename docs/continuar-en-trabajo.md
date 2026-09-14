# Continuar en la PC del trabajo — estado al 2026-09-14

> TL;DR: esta sesión (en la PC de casa) construyó **Cirugías y Ambulancias
> completos** (backend + frontend + catálogos), cerró el pendiente de la
> página CIE-9-MC, y corrigió un bug real de cross-database FK que rompía
> `migrate`. Nada de esto llega a otra PC solo por existir aquí — **hace
> falta commit + push** de la rama `SISEM-15-07-2026` (81 archivos nuevos/
> modificados) para poder hacer `git pull` en el trabajo (ver sección final).
> Este documento es el mapa de continuación, no reemplaza revisar el código.

## Cómo usar este documento

1. En la PC del trabajo, después de `git pull`, corre `python manage.py
   migrate` (ver "Antes de nada" abajo) y revisa que no truene.
2. Lee "Bloqueado — necesita algo de la red del trabajo" primero: son las
   cosas que precisamente AHÍ sí se pueden avanzar (acceso a Oracle/MySQL
   legado que desde casa no había).
3. "Completado" es para no repetir trabajo ni re-preguntar qué ya existe.
4. "Pendiente de decisión" necesita que el usuario (no el asistente) defina
   algo antes de tocar código.

## Antes de nada: correr `migrate`

Cirugías/Ambulancias son apps nuevas, nunca aplicadas en ninguna base de
datos real todavía. En la PC de casa el primer intento de `migrate` falló:

```
psycopg2.errors.UndefinedTable: no existe la relación «cat_clinicas»
```

Causa: usé un `ForeignKey` real de Django hacia `CatClinica`, pero esa
tabla vive en la base de datos **`expedientes`** (ver
`routers.ExpedientesRouter`), físicamente distinta de `default` (donde
viven `cirugias`/`ambulancias`/`catalogos`). Postgres no soporta FK entre
bases de datos distintas. **Ya corregido** en esta misma sesión: la
clínica ahora se guarda como campo plano (`cd_clinica`/
`cd_clinica_origen`, sin FK), igual que el resto del código ya trataba a
`CatClinica`/`CatEmpleado`/`CatFamiliar` (ver `apps/pases/models.py` –
`Referral.no_exp`/`pk_num` — y `apps/contratos_oxigeno/derechohabiente_service.py`).
Las migraciones `cirugias/migrations/0001_initial.py` y
`ambulancias/migrations/0001_initial.py` ya están regeneradas sin ese FK.

Si `migrate` había fallado ahí en la PC de casa, no dejó nada a medias
(Postgres hace rollback de la transacción de la migración que truena) —
correr `migrate` de nuevo después del `git pull` debería aplicar limpio.

## Completado en esta sesión

### Cirugías (agenda quirúrgica) — módulo nuevo completo
- App `backend/apps/cirugias/`: modelos (`SurgerySchedule`,
  `SurgeryDiagnosis`, `SurgeryCancellation`), repository, use_case
  (agendar con validación de no-doble-agenda y no-traslape de horario,
  cancelar con motivo), serializers, views, urls, 2 archivos de tests
  reales (`test_surgery_schedule_api.py`, `test_surgery_report_api.py`).
- Reglas tomadas del legado (`body-agendacir.jsp`): folio síncrono (no el
  token `temporal` del legado), `legacy_folio` como referencia textual
  para una futura migración histórica (pendiente, ver abajo).
- Frontend: `frontend/src/features/cirugias/` (página con lista+filtros,
  diálogo de agendar, diálogo de cancelar), más el reporte
  `ReporteCirugiasPage.tsx`.
- Permisos `clinico:cirugias:read/write`, navegación cableada
  (`/clinico/cirugias`, `/admin/reportes/cirugias`).
- **Fuera de alcance a propósito**: `det_ingcirugia` (cirugías con
  internamiento hospitalario), catálogo de horarios/quirófano físico,
  calendario visual (hoy es lista+filtros).

### Ambulancias (traslados internos) — módulo nuevo completo
- App `backend/apps/ambulancias/`: modelos (`AmbulanceRequest`,
  `AmbulanceRequestSchedule`), repository, use_case (crear solicitud con
  N fechas, autorizar/rechazar con permiso separado de quien solicita,
  cancelar), serializers, views, urls, 3 archivos de tests reales.
- Reemplaza la contraseña `det_clinicas.pw_autoriza` del legado por el
  permiso RBAC `clinico:ambulancias:authorize` — nunca se replicó una
  contraseña en texto plano.
- Frontend: `frontend/src/features/ambulancias/` (lista con filtro de
  autorización, diálogo de alta con fechas dinámicas, autorizar/rechazar),
  más `ReporteAmbulanciasPage.tsx`.
- Permisos `clinico:ambulancias:read/write/authorize`.

### 7 catálogos nuevos de soporte (en `backend/apps/catalogos/`)
Tipos y clasificación de cirugía, motivo de cancelación de cirugía,
motivo/tipo de traslado, tipo de servicio y destino de ambulancia — CRUD
completo + import Excel + permisos, con página de frontend cada uno
(`frontend/src/features/admin/modules/catalogos/<slug>/`).

### Endpoint nuevo: `GET /api/v1/clinicas`
No existía forma de listar `CatClinica` desde el frontend (necesario para
los selects de clínica en Cirugías/Ambulancias). Nuevo
`backend/apps/administracion/views/clinicas_views.py`, solo lectura,
cualquier usuario autenticado.

### CIE-9-MC — cerrado el pendiente de la sesión anterior
Página de frontend construida (`Cie9McPage.tsx`) y entrada de navegación
agregada — antes el backend ya funcionaba pero no había forma de usarlo
desde la UI.

### NOM-024, migración del legado, reportes previos, médicos, perfiles
Sin cambios desde la sesión anterior — sigue todo tal como se documentó
(ver historial de commits/PRs si necesitas el detalle completo; lo nuevo
de hoy es exclusivamente lo de arriba).

## Bloqueado — necesita algo de la red del trabajo

1. **Backup de `his_clinica`** para la migración del historial clínico —
   sigue pendiente, no ha llegado el `mysqldump`.
2. **`inspeccionar_oracle.py`** / **`inspeccionar_legado_mysql.py`** —
   nunca se han podido correr contra los servidores reales.
3. **Comando de migración histórica de `det_cirugia`/`det_ambulancias`**
   — nuevo pendiente de hoy: los modelos ya dejan `legacy_folio` listo
   para esto, pero no hay backup del legado de cirugías/ambulancias
   todavía (mismo bloqueo que el historial clínico).
4. Respaldos completos del runbook (`docs/runbooks/legacy-backup-runbook.md`).

## Pendiente de decisión (el usuario define alcance, no el asistente)

- **Fase 5 (médicos)**: cerrar la ventana de compatibilidad de IDs
  necesita telemetría real de producción (conteo del `WARNING`
  `MEDICO_ID_LEGACY_FALLBACK`).
- **`herramientas`, `movimientos`, `opciones`**: apps vacías, sin alcance
  definido.
- **`farmacia`**: sigue "Discovery" en `docs/architecture/domain-map.md`.
- **Segundo catálogo NOM-024**: confirmar con el certificador cuál es.
- **Cirugías/Ambulancias — mejoras futuras** (no bloqueantes): internamiento
  hospitalario, calendario visual, autorización de ambulancias segmentada
  por clínica, catálogo de horarios de quirófano.
- Correr `python manage.py seed_catalogos_crud_permissions` a mano en el
  próximo deploy (siembra los 28 permisos de los 7 catálogos nuevos; no
  está en el auto-seed de `AdministracionConfig.ready()`).

## IMPORTANTE — esto no viaja solo a la otra PC

Todo el trabajo de esta sesión está **sin commitear** en la rama
`SISEM-15-07-2026` (81 archivos entre nuevos y modificados). Este
documento por sí solo no sirve de nada en la PC del trabajo si el código
no viaja con él. Antes de irte de esta PC:

```
git status   # confirmar qué se va a incluir
git add ...  # o revisar archivo por archivo si hay algo sensible
git commit -m "..."
git push
```

Y en la PC del trabajo: `git fetch && git checkout SISEM-15-07-2026 && git pull`,
después `python manage.py migrate` (ver "Antes de nada" arriba).
