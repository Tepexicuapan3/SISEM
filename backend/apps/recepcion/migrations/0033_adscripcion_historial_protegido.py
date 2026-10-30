"""
P-03: el historial de adscripciones no se puede manipular desde la base.

En PostgreSQL un trigger rechaza DELETE, cualquier cambio a una adscripción
CERRADA y, en una ACTIVA, cualquier cambio que no sea cerrarla. También crea
la vista adscripcion_paciente_cambios: un renglón por cada cambio de clínica o
consultorio (la bitácora, sin duplicar datos). En SQLite (pruebas por
defecto) no aplica y se omite, igual que autorizaciones/0003.
"""

from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION adscripcion_paciente_proteger_historial() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'P-03: las adscripciones no se borran (id %)', OLD.id_adscripcion;
  END IF;
  IF OLD.estatus = 'CERRADA' THEN
    RAISE EXCEPTION 'P-03: una adscripcion cerrada no se modifica (id %)', OLD.id_adscripcion;
  END IF;
  IF (NEW.id_paciente, NEW.id_centro_atencion, NEW.clave_clinica_sermed, NEW.id_consultorio,
      NEW.id_turno, NEW.origen, NEW.fue_sugerida, NEW.fecha_inicio, NEW.id_usuario_creacion)
     IS DISTINCT FROM
     (OLD.id_paciente, OLD.id_centro_atencion, OLD.clave_clinica_sermed, OLD.id_consultorio,
      OLD.id_turno, OLD.origen, OLD.fue_sugerida, OLD.fecha_inicio, OLD.id_usuario_creacion) THEN
    RAISE EXCEPTION 'P-03: solo se permite cerrar la adscripcion (id %)', OLD.id_adscripcion;
  END IF;
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS adscripcion_paciente_proteger_historial_trg ON adscripcion_paciente;
CREATE TRIGGER adscripcion_paciente_proteger_historial_trg
  BEFORE UPDATE OR DELETE ON adscripcion_paciente
  FOR EACH ROW EXECUTE FUNCTION adscripcion_paciente_proteger_historial();

CREATE OR REPLACE VIEW adscripcion_paciente_cambios AS
SELECT *
FROM (
  SELECT
    id_paciente,
    fecha_inicio                                  AS fecha_cambio,
    LAG(clave_clinica_sermed) OVER w              AS clave_clinica_anterior,
    clave_clinica_sermed                          AS clave_clinica_nueva,
    LAG(id_centro_atencion) OVER w                AS id_centro_anterior,
    id_centro_atencion                            AS id_centro_nuevo,
    LAG(id_consultorio) OVER w                    AS id_consultorio_anterior,
    id_consultorio                                AS id_consultorio_nuevo,
    LAG(motivo_cierre) OVER w                     AS motivo_cambio,
    origen,
    id_usuario_creacion                           AS id_usuario_cambio
  FROM adscripcion_paciente
  WINDOW w AS (PARTITION BY id_paciente ORDER BY fecha_inicio)
) cambios
WHERE clave_clinica_anterior IS NOT NULL;
"""

QUITAR = """
DROP VIEW IF EXISTS adscripcion_paciente_cambios;
DROP TRIGGER IF EXISTS adscripcion_paciente_proteger_historial_trg ON adscripcion_paciente;
DROP FUNCTION IF EXISTS adscripcion_paciente_proteger_historial();
"""


# params=None: el SQL va tal cual. Con params=() Django lo pasa por mogrify y
# trata los `%` del RAISE EXCEPTION de plpgsql como parametros (IndexError).
def crear(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREAR, params=None)


def quitar(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(QUITAR, params=None)


class Migration(migrations.Migration):
    dependencies = [("recepcion", "0032_adscripcion")]

    operations = [migrations.RunPython(crear, quitar)]
