"""
P-03: motivo tipificado con el que se cancelan las citas del consultorio
anterior al reasignar. Una fila en cat_motivos_cita; idempotente. La reversa
no la borra (puede haber citas que ya la usan).
"""

from django.db import migrations

NOMBRE = "Cambio de consultorio familiar"


def crear(apps, schema_editor):
    MotivoCita = apps.get_model("catalogos", "MotivoCita")
    if not MotivoCita.objects.filter(name=NOMBRE).exists():
        MotivoCita.objects.create(name=NOMBRE, aplica_a="CANCELACION", is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0045_parametro_anticipacion_checkin"),
        ("recepcion", "0033_adscripcion_historial_protegido"),
    ]

    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
