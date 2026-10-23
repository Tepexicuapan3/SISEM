-- Catalogo de clinicas de la replica "expedientes" (cat_clinicas).
--
-- buscar_expediente (Administracion -> Expedientes, recepcion, vigencia) hace
-- LEFT JOIN cat_clinicas para el nombre de la clinica. Si la tabla no existe la
-- consulta falla y el expediente aparece como "no encontrado" (incidente
-- 2026-10-23: la tabla habia desaparecido de la replica del servidor).
--
-- NO viene de Oracle (ORA-00942 al describir CAT_CLINICAS, 2026-10-22): sale del
-- MySQL del legado (Dump20260903.sql, tabla cat_clinicas, 14 filas). Solo se
-- copian las columnas utiles; SIRES usa cd_clinica y ds_clinica.
--
-- cd_clinica integer: igual que cat_empleados.cd_clinica / cat_familiar.cd_clinica
-- en la replica real (un JOIN integer = varchar falla en Postgres). En un volumen
-- nuevo, 001 ya la crea con varchar y aqui solo se cargan los datos (Postgres
-- convierte el numero a texto al insertar).
--
-- Idempotente:
--   psql -h $EXPEDIENTES_HOST -U $EXPEDIENTES_USER -d $EXPEDIENTES_NAME -f 005_cat_clinicas_datos.sql

CREATE TABLE IF NOT EXISTS cat_clinicas (
    cd_clinica  integer      PRIMARY KEY,
    ds_clinica  varchar(100) NOT NULL,
    ds_folio    varchar(2),
    ds_clues    varchar(45),
    sw_status   varchar(1)
);

INSERT INTO cat_clinicas (cd_clinica, ds_clinica) VALUES
    (1,  'CUAUHTÉMOC'),
    (2,  'TAXQUEÑA'),
    (3,  'TICOMÁN'),
    (4,  'ZARAGOZA'),
    (5,  'HOSPITAL'),
    (6,  'MÉDICO VISITADOR'),
    (7,  'GERENCIA'),
    (8,  'ESPECIALIDAD'),
    (9,  'CLINICA NAPOLES'),
    (10, 'CLINICA NAPOLES ESPECIALIDAD'),
    (11, 'HOSPITAL OBREGON'),
    (12, 'HOSPITAL OBREGON ESPECIALIDAD'),
    (13, 'HOSPITAL AZURA'),
    (14, 'CIMER HEALTH')
ON CONFLICT (cd_clinica) DO NOTHING;
