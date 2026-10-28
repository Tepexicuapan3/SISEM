"""Permisos y menu de la auditoria de solicitudes (2026-10-28).

1. Alta de admin:autorizaciones-auditoria:read / :export en cat_permisos (idempotente).
2. Modulo "Auditoría de autorizaciones" en cat_modulos bajo "administracion",
   ligado al permiso de lectura. Tambien queda en navigation_seed para que
   seed_navigation_menu --prune no lo de de baja.
3. Asigna ambos permisos a los roles administradores activos (cat_roles.is_admin),
   como 0008 y 0014.

Solo agrega filas; la reversa no borra (pueden estar asignados o editados desde la UI).
"""
from django.db import migrations
from django.utils import timezone

PERMISOS = [
    ("admin:autorizaciones-auditoria:read", "Ver la auditoría de solicitudes de autorización (firmas, IP y destinatarios)"),
    ("admin:autorizaciones-auditoria:export", "Exportar a Excel la auditoría de solicitudes de autorización"),
]
CLAVE_MODULO = "administracion.autorizaciones_auditoria"


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
                "titulo": "Auditoría de autorizaciones",
                "icono": "scroll-text",
                "url": "/admin/autorizacion/auditoria",
                "badge": None,
                "orden": 5,
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
        ("autorizaciones", "0014_permisos_y_menu_configuracion"),
        ("administracion", "0018_permisos_recien_nacidos"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
