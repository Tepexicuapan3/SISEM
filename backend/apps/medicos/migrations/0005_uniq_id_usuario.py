# FASE 2 (EXPAND) -- continuación de 0004_expand_surrogate_pk.
#
# Crítico (design, sección 2): al dropear la PK actual en Fase 4
# (0007_switch_surrogate_pk) se destruye su índice único implícito. Sin este
# índice standalone creado de antemano, `id_usuario` queda sin protección de
# unicidad justo en el momento en que pasa a ser nullable. `CONCURRENTLY`
# evita tomar un lock exclusivo largo sobre `cat_medicos` en Postgres real
# (exige migración no atómica y propia -- de ahí que esté separada de 0004).
#
# SQLite no soporta `CONCURRENTLY` (ni beneficio real: es una DB en memoria
# de un solo proceso para tests, sin contención de locks) -- se crea el
# mismo índice único sin esa cláusula. Mismo criterio de portabilidad que
# 0004 (ver su comentario de cabecera).
from django.db import migrations


def create_unique_index_forwards(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                "CREATE UNIQUE INDEX CONCURRENTLY cat_medicos_id_usuario_uniq "
                "ON cat_medicos (id_usuario);"
            )
        else:
            cursor.execute(
                "CREATE UNIQUE INDEX cat_medicos_id_usuario_uniq ON cat_medicos (id_usuario);"
            )


def create_unique_index_backwards(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute("DROP INDEX CONCURRENTLY IF EXISTS cat_medicos_id_usuario_uniq;")
        else:
            cursor.execute("DROP INDEX IF EXISTS cat_medicos_id_usuario_uniq;")


class Migration(migrations.Migration):

    dependencies = [
        ("medicos", "0004_expand_surrogate_pk"),
    ]

    # CREATE INDEX CONCURRENTLY no puede correr dentro de una transacción.
    atomic = False

    operations = [
        migrations.RunPython(create_unique_index_forwards, create_unique_index_backwards),
    ]
