# CatCentroAtencion es managed=False (ver apps/catalogos/models/centros_atencion.py):
# Django nunca vuelve a tocar su esquema fisico por su cuenta, asi que un
# AddField normal actualizaria SOLO el estado de Django (migrations state)
# sin emitir el ALTER TABLE -- la columna nunca existiria fisicamente y
# cualquier SELECT que la toque explotaria con "column cd_clinica_legado
# does not exist". Mismo problema y misma solucion que 0015
# (reconcile_catcentroatencion_drift): SeparateDatabaseAndState con
# state_operations=[AddField] (lo que Django "cree" que tiene el modelo) y
# database_operations=[RunPython] con el DDL real, defensivo via
# _column_exists (reusado tal cual de 0015) para no romper si la columna ya
# existe en algun ambiente.
from django.db import migrations, models


def _column_exists(cursor, connection, table_name, column_name):
    if connection.vendor == "postgresql":
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s "
            "AND table_schema = ANY (current_schemas(false))",
            [table_name, column_name],
        )
        return cursor.fetchone() is not None
    # sqlite (usado por manage.py test, ver settings.py: "if 'test' in
    # sys.argv") no tiene information_schema -- misma pregunta via la
    # introspeccion portable de Django.
    return column_name in {
        col.name
        for col in connection.introspection.get_table_description(cursor, table_name)
    }


def add_column(apps, schema_editor):
    connection = schema_editor.connection
    table = "cat_centros_atencion"
    qn = schema_editor.quote_name

    with connection.cursor() as cursor:
        if not _column_exists(cursor, connection, table, "cd_clinica_legado"):
            cursor.execute(
                f'ALTER TABLE {qn(table)} ADD COLUMN cd_clinica_legado integer NULL;'
            )
        cursor.execute(
            f'CREATE INDEX IF NOT EXISTS cat_centros_atencion_cd_clinica_legado_idx '
            f'ON {qn(table)} (cd_clinica_legado);'
        )


def noop_reverse(apps, schema_editor):
    # No se revierte: la columna podria tener datos reales cargados
    # despues de aplicarse (mismo criterio que 0015).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0028_cattipohospitalizacion_cattipoalta'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='catcentroatencion',
                    name='legacy_cd_clinica',
                    field=models.IntegerField(
                        blank=True, db_column='cd_clinica_legado', db_index=True, null=True,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_column, noop_reverse),
            ],
        ),
    ]
