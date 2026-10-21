"""
cns_bitacora_cambios append-only a nivel de base (NOM-024). Usa la funcion
sires_bitacora_inmutable() de administracion 0014. No tiene FK a usuarios
(el usuario es texto), asi que no hay columnas permitidas: cualquier UPDATE,
DELETE o TRUNCATE se rechaza. En SQLite (tests) no hace nada.
"""
from django.db import migrations

TABLA = "cns_bitacora_cambios"


def crear_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP TRIGGER IF EXISTS {TABLA}_inmutable ON {TABLA};")
        cursor.execute(f"DROP TRIGGER IF EXISTS {TABLA}_sin_truncate ON {TABLA};")
        cursor.execute(
            f"CREATE TRIGGER {TABLA}_inmutable BEFORE UPDATE OR DELETE ON {TABLA} "
            f"FOR EACH ROW EXECUTE FUNCTION sires_bitacora_inmutable();"
        )
        cursor.execute(
            f"CREATE TRIGGER {TABLA}_sin_truncate BEFORE TRUNCATE ON {TABLA} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION sires_bitacora_inmutable();"
        )


def quitar_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP TRIGGER IF EXISTS {TABLA}_inmutable ON {TABLA};")
        cursor.execute(f"DROP TRIGGER IF EXISTS {TABLA}_sin_truncate ON {TABLA};")


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0054_json_columns_to_jsonb"),
        ("administracion", "0014_bitacoras_inmutables"),
    ]

    operations = [
        migrations.RunPython(crear_trigger, quitar_trigger),
    ]
