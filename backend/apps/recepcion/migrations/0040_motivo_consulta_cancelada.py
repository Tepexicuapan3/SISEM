"""
K1 de P-12: motivo tipificado con el que se cancela la cita de seguimiento
cuando se cancela su nota. Una fila en cat_motivos_cita; idempotente. La
reversa no la borra (puede haber citas que ya la usan).
"""

from django.db import migrations

NOMBRE = "Consulta cancelada"


def crear(apps, schema_editor):
    MotivoCita = apps.get_model("catalogos", "MotivoCita")
    if not MotivoCita.objects.filter(name=NOMBRE).exists():
        MotivoCita.objects.create(name=NOMBRE, aplica_a="CANCELACION", is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0021_motivos_cita"),
        ("recepcion", "0039_cita_reprogramada_de"),
    ]

    operations = [
        migrations.RunPython(crear, migrations.RunPython.noop),
    ]
