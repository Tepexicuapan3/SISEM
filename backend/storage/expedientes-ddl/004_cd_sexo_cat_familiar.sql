-- Agrega el sexo a la replica cat_familiar (plan identidad del paciente, Fase 2).
--
-- Oracle CAT_FAMILIAR SI tiene CD_SEXO (verificado 2026-10-22 con
-- `generar_ddl_oracle --tablas-sync`: VARCHAR2(255)) y la replica real del
-- servidor ya la tiene. sync_service.py arma el SELECT a Oracle con las columnas
-- de esta tabla, asi que agregar una columna que Oracle tiene es seguro.
--
-- Solo hace falta en volumenes que se crearon con 001/002 (sin cd_sexo).
-- Idempotente:
--   psql -h $EXPEDIENTES_HOST -U $EXPEDIENTES_USER -d $EXPEDIENTES_NAME -f 004_cd_sexo_cat_familiar.sql
--
-- Las filas existentes quedan con NULL hasta que el boton Actualizar las vuelva
-- a traer (el sync solo actualiza una fila cuando cambia fec_ult_actualizacion).

ALTER TABLE cat_familiar  ADD COLUMN IF NOT EXISTS cd_sexo varchar(255);
ALTER TABLE cat_familiar2 ADD COLUMN IF NOT EXISTS cd_sexo varchar(255);
