"""
P-03 · Reporte de adscritos: permiso atómico de lectura.

No se asigna a ningún rol: lo otorga el administrador desde
Administracion -> Roles, igual que la configuración de P-03 (0019).
Idempotente (get_or_create).
"""
from django.db import migrations
from django.utils import timezone

CODIGO = "admin:reportes:adscripcion:read"
DESCRIPCION = "Ver el reporte de pacientes adscritos por centro, consultorio y turno"


def crear(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")

    # El estado historico de catalogos conserva los nombres de 0001.
    campos = {f.name for f in Permisos._meta.get_fields()}
    activo = "is_active" if "is_active" in campos else "est_activo"
    modificado = "updated_at" if "updated_at" in campos else "fch_modf"

    Permisos.objects.get_or_create(
        codigo=CODIGO,
        defaults={"descripcion": DESCRIPCION, activo: True, "es_sistema": False, modificado: timezone.now()},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0020_permisos_alcance_centro"),
    ]

    operations = [
        # Reversa sin efecto: no se borran asignaciones hechas después.
        migrations.RunPython(crear, migrations.RunPython.noop),
    ]
