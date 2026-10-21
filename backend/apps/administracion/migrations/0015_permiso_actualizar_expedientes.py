"""
Permiso propio para el boton Actualizar de expedientes
(admin:gestion:expedientes:update). Hasta ahora el mismo permiso de lectura
permitia disparar la sincronizacion con SERMED; quien solo consulta ya no
puede escribir en la replica ni en los pacientes (minimo privilegio).

Para no dejar sin el boton a nadie que hoy lo usa, el permiso nuevo se
asigna a los roles que hoy tienen admin:gestion:expedientes:read vigente.
Despues, el administrador se lo quita a los roles que solo deben consultar.
El alta del codigo tambien esta en navigation_permissions_seed (idempotente).
"""
from django.db import migrations
from django.utils import timezone

LECTURA = "admin:gestion:expedientes:read"
ACTUALIZAR = "admin:gestion:expedientes:update"


def asignar(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")

    # El estado historico de catalogos conserva los nombres de 0001
    # (est_activo, fch_modf); el modelo actual los llama is_active/updated_at.
    campos = {f.name for f in Permisos._meta.get_fields()}
    activo = "is_active" if "is_active" in campos else "est_activo"
    modificado = "updated_at" if "updated_at" in campos else "fch_modf"
    permiso, _ = Permisos.objects.get_or_create(
        codigo=ACTUALIZAR,
        defaults={
            "descripcion": "Actualizar expedientes desde SERMED (sincronizacion con Oracle)",
            activo: True,
            "es_sistema": False,
            modificado: timezone.now(),
        },
    )
    roles = (
        RelRolPermiso.objects.filter(id_permiso__codigo=LECTURA, fch_baja__isnull=True)
        .values_list("id_rol_id", flat=True)
        .distinct()
    )
    for id_rol in roles:
        RelRolPermiso.objects.get_or_create(
            id_rol_id=id_rol, id_permiso=permiso, defaults={"fch_baja": None},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0014_bitacoras_inmutables"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [
        # Reversa sin efecto: quitar el permiso a mano si hace falta, para no
        # borrar asignaciones que el administrador haya hecho despues.
        migrations.RunPython(asignar, migrations.RunPython.noop),
    ]
