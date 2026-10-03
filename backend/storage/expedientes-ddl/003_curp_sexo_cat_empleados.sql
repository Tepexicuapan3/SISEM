-- Agrega CURP y sexo a la replica cat_empleados (historia clinica unificada, seccion 5.1:
-- la CURP de los titulares sale de SERMED).
--
-- Oracle CAT_EMPLEADOS SI tiene CURP VARCHAR2(18) y CD_SEXO CHAR(1) (verificado con
-- `inspeccionar_oracle --tabla CAT_EMPLEADOS` el 2026-10-01). sync_service.py arma el SELECT a
-- Oracle con las columnas de esta tabla (information_schema), asi que agregar columnas que
-- Oracle tiene es seguro. Lo que rompio el sync el 2026-09-17 fue una columna que Oracle NO tiene.
--
-- Solo cat_empleados:
--   - cat_familiar NO: Oracle no tiene CURP para familiares (la captura SIRES, cns_paciente.curp).
--   - cat_empleados_sis NO: su tabla en Oracle no se ha inspeccionado.
--
-- Copia EXACTA de Oracle, sin limpiar: CD_SEXO usa F = Femenino y M = Masculino (al reves de la
-- CURP, donde M = Mujer) y hay CURP con el texto 'SIN CURP'. La limpieza y el mapeo del sexo se
-- hacen al copiar a cns_paciente, nunca aqui, porque el sync tambien copia los valores tal cual.
--
-- Las filas que ya existen quedan con NULL hasta correr:
--   python manage.py llenar_curp_empleados
-- (el sync solo actualiza una fila cuando cambia fec_ult_actualizacion).
--
-- Aplicar ANTES de desplegar el codigo que agrega estos campos al modelo CatEmpleado:
--   psql -h $EXPEDIENTES_HOST -U $EXPEDIENTES_USER -d $EXPEDIENTES_NAME -f 003_curp_sexo_cat_empleados.sql
--
-- Reversa (primero revertir el codigo):
--   ALTER TABLE cat_empleados DROP COLUMN IF EXISTS curp, DROP COLUMN IF EXISTS cd_sexo;

ALTER TABLE cat_empleados ADD COLUMN IF NOT EXISTS curp    varchar(18);
ALTER TABLE cat_empleados ADD COLUMN IF NOT EXISTS cd_sexo varchar(1);

CREATE INDEX IF NOT EXISTS ix_cat_empleados_curp ON cat_empleados (curp);
