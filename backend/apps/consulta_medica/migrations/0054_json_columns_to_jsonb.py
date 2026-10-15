"""
Normaliza a jsonb las columnas JSONField de consulta_medica.

Django crea los JSONField como jsonb en Postgres, pero en algunas bases
(restauradas desde dump / scripts SQL) quedaron como `json`. Con `json`,
psycopg ya decodifica el valor y Django vuelve a hacer json.loads() sobre
una list/dict -> TypeError al cargar el modelo (p.ej. get_or_create de
VisitPrescription en POST /visits/<id>/prescription-items).

Idempotente: solo convierte las columnas que hoy sean `json`. En SQLite
(tests) no hace nada.
"""

from django.db import migrations

COLUMNS = [
    ("cns_visit_prescription", "items"),
    ("cns_bitacora_cambios", "valor_anterior"),
    ("cns_bitacora_cambios", "valor_nuevo"),
]


def _convert(schema_editor, from_type, to_type):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for table, column in COLUMNS:
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s AND column_name = %s AND data_type = %s
                """,
                [table, column, from_type],
            )
            if cursor.fetchone() is None:
                continue
            table_sql = schema_editor.quote_name(table)
            column_sql = schema_editor.quote_name(column)
            cursor.execute(
                f"ALTER TABLE {table_sql} ALTER COLUMN {column_sql} "
                f"TYPE {to_type} USING {column_sql}::{to_type}"
            )


def forwards(apps, schema_editor):
    _convert(schema_editor, "json", "jsonb")


def backwards(apps, schema_editor):
    # No se revierte a json: jsonb es el tipo que Django espera.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0053_cancelacion_nota"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
