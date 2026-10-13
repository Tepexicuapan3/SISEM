# `CatMedico.id` pasa a ser el "No. Médico" del legado (ver Engram, topic_key
# sdd/medicos-id-no-medico/design).
#
# - Quita `legacy_cd_medico` y `nombre_display`: el puente legado ahora es
#   `int(code) == CatMedico.id` y el nombre de un médico sin usuario sale de
#   los campos nuevos. En TEST se acepta perder esos datos (el reset reimporta
#   el catálogo); la reversa recrea ambas columnas VACÍAS.
# - Agrega nombre/paterno/materno (80) y cedula_profesional (30, igual que
#   `DetUsuarioCedula.numero`), todos NULL, más el CheckConstraint que los
#   permite solo cuando `id_usuario` es NULL. Se cumple de entrada porque las
#   columnas nuevas nacen en NULL.
# - `ensure_id_sequence` (solo Postgres): defensa ante drift. `0004` creó
#   `id bigserial` (secuencia OWNED), así que normalmente ya existe; si no,
#   la crea, la asocia como DEFAULT y la deja en max(id)+1. En SQLite (tests)
#   hace skip.
#
# Rollback: `migrate medicos 0010`.
from django.db import migrations, models


def ensure_id_sequence(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_serial_sequence('cat_medicos', 'id')")
        seq = cursor.fetchone()[0]
        if seq is None:
            cursor.execute("CREATE SEQUENCE cat_medicos_id_seq OWNED BY cat_medicos.id")
            cursor.execute(
                "ALTER TABLE cat_medicos ALTER COLUMN id "
                "SET DEFAULT nextval('cat_medicos_id_seq')"
            )
            seq = "cat_medicos_id_seq"
        # is_called=false: con la tabla vacía el siguiente nextval devuelve 1.
        cursor.execute(
            "SELECT setval(%s, COALESCE((SELECT MAX(id) FROM cat_medicos), 0) + 1, false)",
            [seq],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('medicos', '0010_add_legacy_cd_medico'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='catmedico',
            name='legacy_cd_medico',
        ),
        migrations.RemoveField(
            model_name='catmedico',
            name='nombre_display',
        ),
        migrations.AddField(
            model_name='catmedico',
            name='nombre',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name='catmedico',
            name='paterno',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name='catmedico',
            name='materno',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name='catmedico',
            name='cedula_profesional',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddConstraint(
            model_name='catmedico',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(id_usuario__isnull=True)
                    | models.Q(
                        nombre__isnull=True,
                        paterno__isnull=True,
                        materno__isnull=True,
                        cedula_profesional__isnull=True,
                    )
                ),
                name='cat_medicos_datos_personales_solo_sin_usuario',
            ),
        ),
        migrations.RunPython(ensure_id_sequence, migrations.RunPython.noop),
    ]
