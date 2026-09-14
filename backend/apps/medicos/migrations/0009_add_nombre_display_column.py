# Fix forward-only para bases donde `medicos.0007_switch_surrogate_pk` YA
# está aplicada SIN el fix de esta sesión (ver cabecera de 0007 y Engram,
# sdd/medico-pk-independiente/design, sección 10.5).
#
# `0007` declara `nombre_display` en `state_operations` (Django ya lo
# conoce desde ahí) pero nunca emitía el `ALTER TABLE ... ADD COLUMN`
# correspondiente en `database_operations` -- gap real, no gap de estado.
# Por eso esta migración es SOLO `RunSQL`, sin `state_operations` ni
# `SeparateDatabaseAndState`: `RunSQL` no toca el estado de Django (no
# implementa un `state_forwards` propio, a diferencia de `AddField`), así
# que no hay riesgo de que Django intente un `AddField` duplicado sobre un
# campo que el estado ya tiene desde `0007`. `makemigrations --check
# --dry-run` se verificó limpio con este archivo en el árbol (ver reporte).
#
# Originalmente `IF NOT EXISTS`/`IF EXISTS` (sintaxis Postgres) para que
# fuera segura de re-correr incluso si la columna ya existiera
# parcialmente (p.ej. alguien la agrego a mano).
#
# SQLite (usado por `manage.py test`, ver `if "test" in sys.argv` en
# settings.py) no soporta `ADD COLUMN IF NOT EXISTS` -- rompe con "near
# EXISTS: syntax error" al crear la base de test desde cero. Y un simple
# `ADD COLUMN` sin condicion tampoco sirve: en SQLite, tras aplicar
# `0007_switch_surrogate_pk`, la columna YA existe (a diferencia de las
# bases Postgres viejas con drift que motivaron este archivo) -- rompe con
# "duplicate column name". La unica forma correcta en ambos motores es
# verificar de verdad si la columna existe antes de tocar nada, via
# introspeccion generica de Django (no SQL crudo especifico de un vendor).
from django.db import migrations

_TABLE = "cat_medicos"
_COLUMN = "nombre_display"


def _column_exists(schema_editor) -> bool:
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, _TABLE)
    return any(col.name == _COLUMN for col in columns)


def add_nombre_display_column(apps, schema_editor):
    if _column_exists(schema_editor):
        return
    schema_editor.execute(f"ALTER TABLE {_TABLE} ADD COLUMN {_COLUMN} varchar(200) NULL;")


def remove_nombre_display_column(apps, schema_editor):
    if not _column_exists(schema_editor):
        return
    schema_editor.execute(f"ALTER TABLE {_TABLE} DROP COLUMN {_COLUMN};")


class Migration(migrations.Migration):

    dependencies = [
        ("medicos", "0008_alter_catmedico_id"),
    ]

    operations = [
        migrations.RunPython(add_nombre_display_column, remove_nombre_display_column),
    ]
