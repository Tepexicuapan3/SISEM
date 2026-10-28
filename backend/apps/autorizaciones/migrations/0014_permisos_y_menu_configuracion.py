"""Permisos y menu de la pantalla de configuracion del modulo (2026-10-28).

1. Alta de admin:autorizaciones-config:read / :update en cat_permisos (idempotente).
2. Modulo "Configuración de autorizaciones" en cat_modulos bajo "administracion",
   ligado al permiso de lectura. Tambien queda en navigation_seed para que
   seed_navigation_menu --prune no lo de de baja.
3. Asigna ambos permisos a los roles administradores activos (cat_roles.is_admin),
   como 0008 hizo con los de autorizadores.

Solo agrega filas; la reversa no borra (pueden estar asignados o editados desde la UI).
"""
from django.db import migrations
from django.utils import timezone

PERMISOS = [
    ("admin:autorizaciones-config:read", "Ver la configuración del módulo de autorizaciones"),
    ("admin:autorizaciones-config:update", "Editar tipos, reglas por centro y motivos de autorizaciones"),
]
CLAVE_MODULO = "administracion.autorizaciones_configuracion"


def _campo(modelo, *opciones):
    nombres = {f.name for f in modelo._meta.get_fields()}
    return next(nombre for nombre in opciones if nombre in nombres)


def crear(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    Roles = apps.get_model("catalogos", "Roles")
    Modulo = apps.get_model("administracion", "Modulo")
    ModuloPermiso = apps.get_model("administracion", "ModuloPermiso")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")

    activo_permiso = _campo(Permisos, "is_active", "est_activo")
    modificado = _campo(Permisos, "updated_at", "fch_modf")
    ahora = timezone.now()
    permisos = {}
    for codigo, descripcion in PERMISOS:
        permisos[codigo], _ = Permisos.objects.get_or_create(
            codigo=codigo,
            defaults={"descripcion": descripcion, activo_permiso: True, "es_sistema": False, modificado: ahora},
        )

    seccion = Modulo.objects.filter(clave="administracion").first()
    if seccion is not None:
        modulo, _ = Modulo.objects.update_or_create(
            clave=CLAVE_MODULO,
            defaults={
                "titulo": "Configuración de autorizaciones",
                "icono": "settings",
                "url": "/admin/autorizacion/configuracion",
                "badge": None,
                "orden": 4,
                "es_seccion": False,
                "grupo": "primary",
                "id_parent": seccion,
                "is_active": True,
                "fch_baja": None,
            },
        )
        ModuloPermiso.objects.get_or_create(id_modulo=modulo, id_permiso=permisos[PERMISOS[0][0]])

    activo_rol = _campo(Roles, "is_active", "est_activo")
    for rol in Roles.objects.filter(is_admin=True, **{activo_rol: True}):
        for permiso in permisos.values():
            relacion, creada = RelRolPermiso.objects.get_or_create(
                id_rol=rol, id_permiso=permiso, defaults={"fch_baja": None},
            )
            if not creada and relacion.fch_baja is not None:
                relacion.fch_baja = None
                relacion.save(update_fields=["fch_baja"])


class Migration(migrations.Migration):
    dependencies = [
        ("autorizaciones", "0013_version_configuracion"),
        ("administracion", "0018_permisos_recien_nacidos"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
