# Continuar en la PC del trabajo — estado al 2026-09-13

> TL;DR: esta sesión (en la PC de casa) avanzó NOM-024, migración del legado,
> reportes, el módulo de médicos completo y los perfiles de personal. Nada
> de esto llega a otra PC solo por existir aquí — **hace falta commit +
> push** de la rama `SISEM-15-07-2026` para poder hacer `git pull` en el
> trabajo (ver sección final). Este documento es el mapa de continuación,
> no reemplaza revisar el código.

## Cómo usar este documento

1. En la PC del trabajo, después de `git pull`, lee la sección
   "Bloqueado — necesita algo de la red del trabajo" primero: son las
   cosas que precisamente AHÍ sí se pueden avanzar (acceso a Oracle/MySQL
   legado que desde casa no había).
2. La sección "Completado" es para no repetir trabajo ni re-preguntar qué
   ya existe.
3. La sección "Pendiente de decisión" necesita que el usuario (no el
   asistente) defina algo antes de tocar código.

## Completado en esta sesión

### NOM-024-SSA3
- **CURP**: campo agregado a `CatEmpleado`/`CatFamiliar`
  (`backend/apps/administracion/models/empleado.py`, `familiar.py`) +
  columna en `backend/storage/expedientes-ddl/002_tablas_faltantes_expediente.sql`.
  Sin confirmar todavía si Oracle ya la captura (usar
  `inspeccionar_oracle --tabla cat_empleados --tabla cat_familiar` cuando
  haya red).
- **Catálogo CIE-9-MC**: modelo, migración, import masivo (Excel) e
  integración con `CATALOG_IMPORT_REGISTRY` — todo el backend en
  `backend/apps/catalogos/models/cie9_mc.py` y archivos relacionados.
  **Falta la página del frontend** (ver "Pendiente" abajo) y cargar los
  códigos reales (archivo oficial DGIS/CENETEC).
- **Política de retención**: `docs/governance/nom024-retention-policy.md`.
- **Bug corregido**: `backend/storage/expedientes-ddl/002_tablas_faltantes_expediente.sql`
  agrega `cat_empleados_sis`, `cat_familiar2` y `dnt_licencias_medicas`, que
  el código ya esperaba sincronizar pero no existían (las licencias médicas
  probablemente no se estaban guardando).

### Migración del legado (java-main)
- **Herramientas de inspección** (solo lectura, listas para correr con
  red real):
  - `backend/apps/administracion/management/commands/inspeccionar_oracle.py`
  - `backend/apps/authentication/management/commands/inspeccionar_legado_mysql.py`
- **Comando de migración de historial clínico**, ya escrito y con 6 tests
  (mockeando la conexión MySQL):
  `backend/apps/consulta_medica/management/commands/migrar_historial_clinico_legacy.py`
  — migra `his_clinica` → `ClinicalHistory`, resolviendo catálogos por
  NOMBRE (no por id crudo, los ids del legado no coinciden con los de
  SISEM). **Bloqueado**: esperando el backup (`mysqldump`) de
  `his_clinica` + `cat_ocupacion`/`cat_escolaridad`/`cat_edocivil`/
  `cat_religion`/`cat_residencia` (pedido explícito al usuario, ver abajo).
  También se identificó que `his_clinicad` (tabla separada) es el
  historial DENTAL, ya mapeado por el equipo a `StomatologyHistory` — no
  hay comando de migración para esa todavía.
- **Runbook de respaldo**: `docs/runbooks/legacy-backup-runbook.md` — antes
  de tocar/decomisionar cualquier servidor legado.
- Migración de usuarios ya existía de antes:
  `backend/apps/authentication/management/commands/migrar_usuarios_legacy.py`
  (refactorizada para compartir base con las de arriba vía
  `_legacy_mysql_base.py`).

### Reportes (nuevo módulo, antes solo un placeholder muerto)
- **Informe Diario de Consulta Médica**: `GET /api/v1/reportes/consultas/diario`
  (+ `?export=xlsx`). Backend en `backend/apps/consulta_medica/uses_case/daily_report_usecase.py`.
- **Informe de Pases**: `GET /api/v1/reportes/pases` (+ export). Backend en
  `backend/apps/pases/uses_case/referral_usecase.py`.
- Ambos con página real en el frontend
  (`frontend/src/features/admin/modules/reportes/pages/`), menú lateral
  cableado (`navigation_seed.py` + `nav-config.ts` + router).
- Inventario completo de qué reportes/documentos tenía el legado:
  `docs/architecture/legacy-reports-inventory.md` — útil para elegir el
  siguiente reporte a construir (candidatos: incapacidades, farmacia/insumos).

### Módulo de médicos — auditoría completa + arreglos
- **Permisos**: se sembraron los 5 que faltaban (`create`, `update`,
  `horarios`, `excepciones`, `coberturas` — solo `read` existía).
- **Coberturas**: antes solo tenía `POST`; se agregó `GET` (listar) y
  `DELETE` (cancelar) + pestaña completa en el frontend
  (`MedicoCoberturasTab.tsx`).
- **24 tests nuevos** (antes casi no había: solo creación/búsqueda).
- **Arquitectura refactorizada**: `medico_views.py` bajó de 887 a 410
  líneas; la lógica se movió a `backend/apps/medicos/{repositories,uses_case,presenters.py,serializers.py}`,
  siguiendo la regla propia del proyecto ("lógica crítica en use_cases,
  nunca en transport"). Dos apps externas (`recepcion/views/citas_views.py`,
  `agenda_views.py`) se actualizaron porque importaban directo de
  `medico_views.py`.
- **Pendiente, bloqueado**: cerrar la "Fase 5" (ventana de compatibilidad
  de IDs médico/usuario) — necesita el conteo real del `WARNING`
  `MEDICO_ID_LEGACY_FALLBACK` en logs de producción, no se puede decidir
  sin esa telemetría.

### Perfiles de personal (médico/enfermería/administrativo)
- Backend: `PATCH /api/v1/users/:id` acepta `perfilMedico`/
  `perfilEnfermeria`/`perfilAdministrativo` (anidado en gestión de
  usuarios, reutiliza permisos existentes).
- Frontend: nueva sección `PerfilesSection.tsx` en el formulario de
  edición de usuario, con switch on/off por perfil. Completo end-to-end.

## Bloqueado — necesita algo de la red del trabajo

Esto es exactamente lo que SÍ se puede avanzar estando en la PC del
trabajo (con acceso a la red interna que desde casa no hay):

1. **Correr `inspeccionar_oracle.py`** contra Oracle real:
   ```
   python manage.py inspeccionar_oracle --tabla cat_empleados --tabla cat_familiar --tabla cat_empleados_sis --tabla cat_familiar2 --tabla dnt_licencias_medicas
   ```
   Confirma si CURP ya existe en Oracle y las columnas reales de las 3
   tablas que se completaron "a lo seguro" en `002_tablas_faltantes_expediente.sql`.

2. **Backup de `his_clinica`** (para poder correr por fin la migración del
   historial clínico):
   ```
   mysqldump --host=<HOST> --port=3306 --user=<USUARIO> --password \
     --no-tablespaces --single-transaction \
     dbclinicas his_clinica cat_ocupacion cat_escolaridad cat_edocivil cat_religion cat_residencia \
     > his_clinica_backup.sql
   ```
   Confirmar antes el nombre real de la base (se asumió `dbclinicas`) y el
   host (se usó `10.15.15.61`, visto en metadata de un dump de
   procedimientos, pero no confirmado como el host correcto de
   `his_clinica`). Guardar el archivo en `backend/storage/legacy-backups/`
   (crear la carpeta) o avisar la ruta.

3. **Correr `inspeccionar_legado_mysql.py`** contra `dbclinicas`/`sides`/
   `fotosys`/`nominad`/`ws_stc` para tener el inventario real de tablas —
   sigue pendiente, nunca se pudo ejecutar.

4. **Hacer los respaldos completos** del runbook
   (`docs/runbooks/legacy-backup-runbook.md`) antes de que alguien apague
   un servidor legado — sigue siendo solo un documento, nadie lo ha
   ejecutado.

## Pendiente de decisión (el usuario define alcance, no el asistente)

- **Página de frontend para CIE-9-MC**: el backend ya funciona
  (`/api/v1/cie9-mc` vía el import masivo genérico), pero nunca se
  construyó la pantalla — para no dejar un link roto en el menú, no se
  agregó la entrada de navegación tampoco. Es la más rápida de cerrar.
- **Cirugías** y **ambulancias**: módulos clínicos completos que no
  existen en SISEM.
- **`herramientas`, `movimientos`, `opciones`**: apps de Django vacías
  (scaffolding sin una sola línea) — nadie ha dicho qué deben hacer.
- **`farmacia`**: sigue en estado "Discovery" en
  `docs/architecture/domain-map.md`, sin ownership formal.
- **Segundo catálogo NOM-024** (más allá de CIE-9-MC): pendiente confirmar
  con el certificador cuál es el que realmente exige la norma vigente.
- Reportes adicionales candidatos: incapacidades/licencias,
  farmacia/insumos (ver `docs/architecture/legacy-reports-inventory.md`).

## IMPORTANTE — esto no viaja solo a la otra PC

Todo el trabajo de esta sesión está **sin commitear** en la rama
`SISEM-15-07-2026` (76 archivos entre nuevos y modificados). Este
documento por sí solo no sirve de nada en la PC del trabajo si el código
no viaja con él. Antes de irte de esta PC:

```
git status   # confirmar qué se va a incluir
git add ...  # o revisar archivo por archivo si hay algo sensible
git commit -m "..."
git push
```

Y en la PC del trabajo: `git fetch && git checkout SISEM-15-07-2026 && git pull`.
