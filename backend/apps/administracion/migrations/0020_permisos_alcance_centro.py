"""
Alcance por centro de atención: permisos atómicos.

Ninguno se asigna a roles existentes: el administrador los otorga desde
Administracion -> Roles a quien corresponda. El rol administrador ya los
tiene por `*`. Idempotente (get_or_create), mismo patrón que 0019.
"""
from django.db import migrations
from django.utils import timezone

SIN_ASIGNAR = (
    ("alcance:centros:todos", "Ver y trabajar la información de todos los centros de atención"),
    ("recepcion:citas:agendar_otros_centros", "Agendar citas en consultorios de otros centros de atención"),
)


def crear(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")

    # El estado historico de catalogos conserva los nombres de 0001.
    campos = {f.name for f in Permisos._meta.get_fields()}
    activo = "is_active" if "is_active" in campos else "est_activo"
    modificado = "updated_at" if "updated_at" in campos else "fch_modf"

    for codigo, descripcion in SIN_ASIGNAR:
        Permisos.objects.get_or_create(
            codigo=codigo,
            defaults={"descripcion": descripcion, activo: True, "es_sistema": False, modificado: timezone.now()},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0019_permisos_consultorio_familiar"),
    ]

    operations = [
        migrations.RunPython(crear, migrations.RunPython.noop),
    ]
