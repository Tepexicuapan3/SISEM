"""Permisos atomicos de la bandeja de autorizaciones (mismo patron que 0004).

Tener el permiso no basta: para decidir, ademas, la politica del autorizador
(estatus, vigencia, tipo y centro) debe permitirlo en ese momento.
"""
from django.db import migrations
from django.utils import timezone

PERMISOS = [
    ("clinico:autorizaciones:read", "Ver la bandeja y el detalle de solicitudes de autorización"),
    ("clinico:autorizaciones:decide", "Autorizar o rechazar solicitudes (requiere ser autorizador vigente)"),
    ("clinico:autorizaciones:notify", "Enviar solicitudes de autorización a autorizadores elegidos"),
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
        ("autorizaciones", "0006_solicitudes_solo_insercion"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
