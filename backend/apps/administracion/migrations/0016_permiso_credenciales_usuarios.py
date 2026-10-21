"""
Permiso propio para credenciales de usuarios
(admin:gestion:usuarios:credenciales): restablecer contrasena, forzar cierre
de sesion y desbloquear. Antes colgaban de admin:gestion:usuarios:update, el
mismo que permite editar usuarios (change auth-session-revocation).

Se asigna SOLO a los roles administradores (is_admin=True, vigentes). Idempotente.
El alta del codigo tambien esta en navigation_permissions_seed.
"""
from django.db import migrations
from django.utils import timezone

CREDENCIALES = "admin:gestion:usuarios:credenciales"
DESCRIPCION = (
    "Gestionar credenciales de usuarios: restablecer contrasena, "
    "forzar cierre de sesion y desbloquear"
)


def asignar(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    Roles = apps.get_model("catalogos", "Roles")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")

    # El estado historico de catalogos conserva los nombres de 0001
    # (est_activo, fch_modf); el modelo actual los llama is_active/updated_at.
    campos = {f.name for f in Permisos._meta.get_fields()}
    activo = "is_active" if "is_active" in campos else "est_activo"
    modificado = "updated_at" if "updated_at" in campos else "fch_modf"
    permiso, _ = Permisos.objects.get_or_create(
        codigo=CREDENCIALES,
        defaults={
            "descripcion": DESCRIPCION,
            activo: True,
            "es_sistema": False,
            modificado: timezone.now(),
        },
    )
    rol_campos = {f.name for f in Roles._meta.get_fields()}
    rol_activo = "is_active" if "is_active" in rol_campos else "est_activo"
    for rol in Roles.objects.filter(is_admin=True, **{rol_activo: True}):
        RelRolPermiso.objects.get_or_create(
            id_rol=rol, id_permiso=permiso, defaults={"fch_baja": None},
        )


def quitar(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")
    permiso = Permisos.objects.filter(codigo=CREDENCIALES).first()
    if permiso is None:
        return
    RelRolPermiso.objects.filter(id_permiso=permiso).delete()
    permiso.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0015_permiso_actualizar_expedientes"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [
        migrations.RunPython(asignar, quitar),
    ]
