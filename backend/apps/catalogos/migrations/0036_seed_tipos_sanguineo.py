"""
5.2 (grupo sanguineo): siembra cat_tpsanguineo con los 8 tipos y los MISMOS
codigos que el legado (dbclinicas.cat_tpsanguineo, dump 2026-09-03), para que
una migracion futura del legado use el codigo tal cual.

Idempotente y sin pisar lo capturado a mano en el CRUD del catalogo: si el
nombre ya existe (con cualquier id) no se duplica, y el id del legado solo se
usa si esta libre. Los datos viven inline a proposito.
"""
from django.core.management.color import no_style
from django.db import migrations

# (id en dbclinicas.cat_tpsanguineo, nombre). Orden y codigos del legado.
LEGACY_BLOOD_TYPES = (
    (1, "A+"),
    (2, "B-"),
    (3, "A-"),
    (4, "B+"),
    (5, "AB+"),
    (6, "AB-"),
    (7, "O+"),
    (8, "O-"),
)


def _norm(name):
    # "O +", "o+" y el signo menos tipografico cuentan como el mismo tipo.
    return (name or "").replace("−", "-").replace(" ", "").upper()


def seed_blood_types(apps, schema_editor):
    TiposSanguineo = apps.get_model("catalogos", "TiposSanguineo")
    existing = {_norm(name) for name in TiposSanguineo.objects.values_list("name", flat=True)}

    used_explicit_id = False
    for legacy_id, name in LEGACY_BLOOD_TYPES:
        if _norm(name) in existing:
            continue
        if TiposSanguineo.objects.filter(pk=legacy_id).exists():
            TiposSanguineo.objects.create(name=name)
        else:
            TiposSanguineo.objects.create(pk=legacy_id, name=name)
            used_explicit_id = True

    # Con ids explicitos la secuencia de Postgres no avanza: sin esto, la
    # siguiente alta desde el CRUD chocaria con la llave primaria.
    if used_explicit_id:
        connection = schema_editor.connection
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), [TiposSanguineo]):
                cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0035_cat_perfil_acceso"),
    ]

    operations = [
        migrations.RunPython(seed_blood_types, migrations.RunPython.noop),
    ]
