"""El historial de autorizadores es append-only (NOM-024: trazabilidad que no
se puede manipular). En PostgreSQL un trigger rechaza UPDATE y DELETE; en
SQLite (pruebas por defecto) no aplica y se omite.
"""
from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION aut_rechaza_modificacion() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'La tabla % es de solo insercion: % no esta permitido', TG_TABLE_NAME, TG_OP;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS aut_autorizador_movimiento_solo_insercion ON aut_autorizador_movimiento;
CREATE TRIGGER aut_autorizador_movimiento_solo_insercion
  BEFORE UPDATE OR DELETE ON aut_autorizador_movimiento
  FOR EACH ROW EXECUTE FUNCTION aut_rechaza_modificacion();
"""

QUITAR = """
DROP TRIGGER IF EXISTS aut_autorizador_movimiento_solo_insercion ON aut_autorizador_movimiento;
DROP FUNCTION IF EXISTS aut_rechaza_modificacion();
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
    dependencies = [("autorizaciones", "0002_datos_iniciales")]

    operations = [migrations.RunPython(crear, quitar)]
