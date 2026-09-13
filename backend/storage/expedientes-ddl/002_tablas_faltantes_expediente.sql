-- Completa el esquema de la BD "expedientes" para que coincida con lo que
-- apps.administracion.use_cases.expedientes.actualizar_expediente.TABLAS_SYNC espera
-- sincronizar. Antes de este archivo, 001_schema.sql solo creaba 4 de las 6 tablas
-- (cat_empleados_sis, cat_familiar2 y dnt_licencias_medicas faltaban), lo que hacía que
-- el sync de licencias médicas y de los duplicados "_sis"/"2" fallara o no persistiera nada.
--
-- Igual que 001_schema.sql: nombres de columna en minusculas y sin comillas a proposito
-- (sync_service.py descubre columnas via information_schema.columns sin comillas).
--
-- Este archivo solo corre automaticamente en un volumen Postgres NUEVO (mecanismo
-- docker-entrypoint-initdb.d, ver docker-compose.yml / docker-compose.local.yml). Sobre una
-- base "expedientes" ya inicializada hay que aplicarlo a mano, p. ej.:
--   psql -h $EXPEDIENTES_HOST -U $EXPEDIENTES_USER -d $EXPEDIENTES_NAME -f 002_tablas_faltantes_expediente.sql

-- ── CURP (NOM-024-SSA3: identificador de paciente para intercambio de informacion) ─────────────
-- IMPORTANTE: agregar la columna aqui es seguro y aditivo, pero para que el sync la traiga sola
-- (sync_service.py replica columnas de Postgres por nombre desde Oracle) hace falta confirmar
-- primero, con `python manage.py inspeccionar_oracle --tabla cat_empleados --tabla cat_familiar`,
-- que la tabla origen en Oracle realmente tiene una columna equivalente. Si Oracle no la tiene
-- capturada, esta columna queda disponible para captura manual desde administracion mientras
-- se resuelve el gap en el sistema de RH (Oracle/SERMED).
ALTER TABLE cat_empleados ADD COLUMN IF NOT EXISTS curp varchar(18);
ALTER TABLE cat_familiar  ADD COLUMN IF NOT EXISTS curp varchar(18);

-- ── cat_empleados_sis ────────────────────────────────────────────────────────────────────────
-- Mismo shape que cat_empleados (el nombre "_sis" sugiere la misma entidad desde otra fuente/
-- sistema). Aditivo y de bajo riesgo: si el resultado de `inspeccionar_oracle` muestra columnas
-- distintas, se amplia despues sin romper nada de lo ya sincronizado.
CREATE TABLE IF NOT EXISTS cat_empleados_sis (
    no_exp                 varchar(20) PRIMARY KEY,
    ds_paterno             varchar(100),
    ds_materno             varchar(100),
    ds_nombre              varchar(100),
    cd_laboral             varchar(100),
    cve_cd_laboral         varchar(10),
    cve_baja               varchar(10),
    fec_baja               date,
    fe_nac                 date,
    fec_vig                date,
    no_edad                integer,
    cd_clinica             varchar(10),
    curp                   varchar(18),
    fec_ult_actualizacion  timestamp
);

-- ── cat_familiar2 ────────────────────────────────────────────────────────────────────────────
-- Mismo shape que cat_familiar, misma logica que cat_empleados_sis.
CREATE TABLE IF NOT EXISTS cat_familiar2 (
    pk_num                 integer PRIMARY KEY,
    no_expf                varchar(20) NOT NULL,
    ds_paterno             varchar(100),
    ds_materno             varchar(100),
    ds_nombre              varchar(100),
    cd_parentesco          varchar(50),
    tp_der                 varchar(2),
    fe_nac                 date,
    no_edad                integer,
    fec_vig                date,
    cd_clinica             varchar(10),
    curp                   varchar(18),
    fec_ult_actualizacion  timestamp
);

-- ── dnt_licencias_medicas ────────────────────────────────────────────────────────────────────
-- OJO: a diferencia de las tablas anteriores, aqui SOLO se declaran las columnas que ya conoce
-- TABLAS_SYNC (no_folio como llave, no_exp para filtrar por expediente, fec_ult_actualizacion
-- para el diff incremental). NO se inventan columnas de negocio (tipo de licencia, fechas de
-- inicio/fin, dias, diagnostico, medico que la emite, etc.) porque es un registro clinico real:
-- adivinarlas arriesga capturar mal o perder informacion. Antes de dar por completa esta tabla,
-- correr:
--   python manage.py inspeccionar_oracle --tabla dnt_licencias_medicas
-- y ampliar esta tabla con las columnas reales que reporte Oracle.
CREATE TABLE IF NOT EXISTS dnt_licencias_medicas (
    no_folio               varchar(20) PRIMARY KEY,
    no_exp                 varchar(20) NOT NULL,
    fec_ult_actualizacion  timestamp
);

CREATE INDEX IF NOT EXISTS idx_cat_empleados_sis_cd_clinica ON cat_empleados_sis (cd_clinica);
CREATE INDEX IF NOT EXISTS idx_cat_familiar2_no_expf ON cat_familiar2 (no_expf);
CREATE INDEX IF NOT EXISTS idx_dnt_licencias_medicas_no_exp ON dnt_licencias_medicas (no_exp);
