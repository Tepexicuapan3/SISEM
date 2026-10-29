"""Parametro citas.anticipacion_checkin_min: minutos antes de la hora de la
cita en que el paciente tiene que haber hecho su check-in. Pasado ese
limite no se lo atiende con la cita y queda en no_asistio.

Idempotente por clave, igual que 0043: si ya existe no se toca.
"""
from decimal import Decimal

from django.db import migrations

DEFINICION = {
    "key": "citas.anticipacion_checkin_min",
    "description": "Minutos antes de la hora de la cita en que el paciente tiene que presentarse "
                   "(check-in). Si llega después, no se lo atiende y la cita queda en No asistió.",
    "module": "citas",
    "value_type": "ENTERO",
    "general_value": "30",
    "min_value": Decimal("0"), "max_value": Decimal("240"),
    "allows_center_override": False,
    "legacy_source": None,
}


def seed(apps, schema_editor):
    Definicion = apps.get_model("catalogos", "ParametroDefinicion")
    Definicion.objects.get_or_create(key=DEFINICION["key"], defaults=DEFINICION)


def unseed(apps, schema_editor):
    Definicion = apps.get_model("catalogos", "ParametroDefinicion")
    Centro = apps.get_model("catalogos", "ParametroCentro")
    Centro.objects.filter(definition__key=DEFINICION["key"]).delete()
    Definicion.objects.filter(key=DEFINICION["key"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
