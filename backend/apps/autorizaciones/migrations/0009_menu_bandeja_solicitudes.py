"""Menu lateral: "Solicitudes de autorización" en la seccion Clinico, ligado a
clinico:autorizaciones:read (los roles admin ya lo tienen desde 0008).

Idempotente; si la seccion "clinico" aun no existe (base sin seed de menu)
se omite: la crea seed_navigation_menu, donde tambien quedo registrada.
"""
from django.db import migrations

CLAVE_MODULO = "clinico.autorizaciones_solicitudes"


def crear(apps, schema_editor):
    Modulo = apps.get_model("administracion", "Modulo")
    ModuloPermiso = apps.get_model("administracion", "ModuloPermiso")
    Permisos = apps.get_model("catalogos", "Permisos")

    seccion = Modulo.objects.filter(clave="clinico").first()
    if seccion is None:
        return
    modulo, _ = Modulo.objects.update_or_create(
        clave=CLAVE_MODULO,
        defaults={
            "titulo": "Solicitudes de autorización",
            "icono": "clipboard-list",
            "url": "/clinico/autorizaciones",
            "badge": None,
            "orden": 6,
            "es_seccion": False,
            "grupo": "primary",
            "id_parent": seccion,
            "is_active": True,
            "fch_baja": None,
        },
    )
    permiso = Permisos.objects.filter(codigo="clinico:autorizaciones:read").first()
    if permiso is not None:
        ModuloPermiso.objects.get_or_create(id_modulo=modulo, id_permiso=permiso)


class Migration(migrations.Migration):
    dependencies = [("autorizaciones", "0008_menu_y_permisos_admin")]

    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
