"""Decisiones firmadas y transiciones de estado son de solo insercion (NOM-024:
trazabilidad no manipulable). Reutiliza la funcion aut_rechaza_modificacion()
creada en 0003. Solo PostgreSQL; en SQLite (pruebas por defecto) se omite.
"""
from django.db import migrations

TABLAS = ("aut_solicitud_decision", "aut_solicitud_transicion")


def crear(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for tabla in TABLAS:
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {tabla}_solo_insercion ON {tabla};"
            f"CREATE TRIGGER {tabla}_solo_insercion BEFORE UPDATE OR DELETE ON {tabla} "
            f"FOR EACH ROW EXECUTE FUNCTION aut_rechaza_modificacion();",
            params=None,
        )


def quitar(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for tabla in TABLAS:
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {tabla}_solo_insercion ON {tabla};", params=None)


class Migration(migrations.Migration):
    dependencies = [("autorizaciones", "0005_tablas_solicitudes")]

    operations = [migrations.RunPython(crear, quitar)]
