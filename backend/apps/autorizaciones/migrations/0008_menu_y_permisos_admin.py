"""Menu lateral y permisos de administrador del modulo de autorizaciones.

1. Alta del modulo "Autorizadores médicos" en cat_modulos (el menu lateral se
   arma desde la base) bajo la seccion "administracion", ligado a
   admin:autorizadores:read.
2. Asigna TODOS los permisos del modulo a los roles administradores activos
   (cat_roles.is_admin), igual que seed_navigation_permissions hace con los
   catalogos administrativos.

Idempotente. Si la seccion "administracion" aun no existe (base recien
creada, sin seed de menu), el modulo se omite: lo crea seed_navigation_menu,
donde tambien quedo registrado para que --prune no lo de de baja.
"""
from django.db import migrations

CLAVE_MODULO = "administracion.autorizadores_medicos"

PERMISOS_ADMIN = [
    "admin:autorizadores:read",
    "admin:autorizadores:create",
    "admin:autorizadores:update",
    "admin:autorizadores:status",
    "admin:autorizadores:global",
    "clinico:autorizaciones:read",
    "clinico:autorizaciones:decide",
    "clinico:autorizaciones:notify",
]


def _campo(modelo, *opciones):
    nombres = {f.name for f in modelo._meta.get_fields()}
    return next(nombre for nombre in opciones if nombre in nombres)


def crear(apps, schema_editor):
    Modulo = apps.get_model("administracion", "Modulo")
    ModuloPermiso = apps.get_model("administracion", "ModuloPermiso")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")
    Permisos = apps.get_model("catalogos", "Permisos")
    Roles = apps.get_model("catalogos", "Roles")

    permisos = {p.codigo: p for p in Permisos.objects.filter(codigo__in=PERMISOS_ADMIN)}

    seccion = Modulo.objects.filter(clave="administracion").first()
    if seccion is not None:
        modulo, _ = Modulo.objects.update_or_create(
            clave=CLAVE_MODULO,
            defaults={
                "titulo": "Autorizadores médicos",
                "icono": "user-check",
                "url": "/admin/autorizacion/autorizadores",
                "badge": None,
                "orden": 3,
                "es_seccion": False,
                "grupo": "primary",
                "id_parent": seccion,
                "is_active": True,
                "fch_baja": None,
            },
        )
        lectura = permisos.get("admin:autorizadores:read")
        if lectura is not None:
            ModuloPermiso.objects.get_or_create(id_modulo=modulo, id_permiso=lectura)

    activo = _campo(Roles, "is_active", "est_activo")
    for rol in Roles.objects.filter(is_admin=True, **{activo: True}):
        for permiso in permisos.values():
            relacion, creada = RelRolPermiso.objects.get_or_create(
                id_rol=rol, id_permiso=permiso, defaults={"fch_baja": None},
            )
            if not creada and relacion.fch_baja is not None:
                relacion.fch_baja = None
                relacion.save(update_fields=["fch_baja"])


class Migration(migrations.Migration):
    dependencies = [
        ("autorizaciones", "0007_permisos_solicitudes"),
        ("administracion", "0018_permisos_recien_nacidos"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    # Reversa sin borrado: el menu y las asignaciones pueden editarse despues desde la UI.
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
