"""
Alcance por centro: rellena el centro de las visitas y citas que ya existían.

Mismo criterio que al crear (services/alcance_centro.centro_de_registro): el
centro del consultorio y, sin consultorio, el centro de quien la registró.
Solo llena filas con centro vacío; no cambia ninguna que ya lo tenga.
Reversa sin efecto: la columna se borra con la reversa de 0035.
"""
from django.db import migrations
from django.db.models import OuterRef, Subquery


def rellenar(apps, schema_editor):
    Consultorios = apps.get_model("catalogos", "Consultorios")
    DetUsuario = apps.get_model("authentication", "DetUsuario")

    centro_del_consultorio = Subquery(
        Consultorios.objects.filter(pk=OuterRef("consultorio_id")).values("id_center_id")[:1]
    )
    centro_de_quien_registro = Subquery(
        DetUsuario.objects.filter(id_usuario_id=OuterRef("created_by_id")).values("id_centro_atencion_id")[:1]
    )
    for nombre in ("Visit", "CitaMedica"):
        modelo = apps.get_model("recepcion", nombre)
        modelo.objects.filter(centro__isnull=True, consultorio__isnull=False).update(centro_id=centro_del_consultorio)
        modelo.objects.filter(centro__isnull=True, created_by_id__isnull=False).update(centro_id=centro_de_quien_registro)


class Migration(migrations.Migration):

    dependencies = [
        ("recepcion", "0035_centro_en_visitas_y_citas"),
    ]

    operations = [
        migrations.RunPython(rellenar, migrations.RunPython.noop),
    ]
