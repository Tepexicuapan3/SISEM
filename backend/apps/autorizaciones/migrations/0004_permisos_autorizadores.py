"""Alta de los permisos atomicos de administracion de autorizadores.

Mismo patron que administracion/0017: idempotente (get_or_create) y NO asigna
ningun permiso a ningun rol; el rol comodin ("*") ya los tiene y al resto se
asignan desde la matriz de roles. `global` va aparte a proposito: otorgar
alcance a todos los centros no se hereda de `update`.
"""
from django.db import migrations
from django.utils import timezone

PERMISOS = [
    ("admin:autorizadores:read", "Ver autorizadores médicos, su historial y sus asignaciones"),
    ("admin:autorizadores:create", "Dar de alta autorizadores médicos"),
    ("admin:autorizadores:update", "Editar tipos, centros y renovar la vigencia de autorizadores médicos"),
    ("admin:autorizadores:status", "Suspender, reactivar y dar de baja autorizadores médicos"),
    ("admin:autorizadores:global", "Otorgar alcance GLOBAL (todos los centros) a autorizadores médicos"),
]


def _campos(modelo):
    nombres = {f.name for f in modelo._meta.get_fields()}
    activo = "is_active" if "is_active" in nombres else "est_activo"
    modificado = "updated_at" if "updated_at" in nombres else "fch_modf"
    return activo, modificado


def crear(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    activo, modificado = _campos(Permisos)
    ahora = timezone.now()
    for codigo, descripcion in PERMISOS:
        Permisos.objects.get_or_create(
            codigo=codigo,
            defaults={"descripcion": descripcion, activo: True, "es_sistema": False, modificado: ahora},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("autorizaciones", "0003_historial_solo_insercion"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    # Reversa sin borrado: los permisos pueden estar ya asignados a roles.
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
