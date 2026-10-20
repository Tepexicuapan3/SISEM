"""Definiciones iniciales de parametros: SOLO las que el codigo ya lee.

Idempotente por clave: si la definicion existe no se toca (un admin pudo
haber cambiado el valor). Los topes de citas toman el valor general de
settings al momento de migrar, para no cambiar lo que hoy configura el
entorno (.env) de cada servidor.
"""
from decimal import Decimal

from django.conf import settings
from django.db import migrations


def _definitions():
    return [
        {
            "key": "citas.max_por_paciente_dia",
            "description": "Máximo de citas activas por paciente en un mismo día (0 = sin tope)",
            "module": "citas",
            "value_type": "ENTERO",
            "general_value": str(getattr(settings, "CITAS_MAX_POR_PACIENTE_DIA", 1)),
            "min_value": Decimal("0"), "max_value": Decimal("10"),
            "allows_center_override": False,
            "legacy_source": "regla legado P-06",
        },
        {
            "key": "citas.max_por_expediente_dia",
            "description": "Máximo de citas activas por expediente (titular y familiares) en un día (0 = sin tope)",
            "module": "citas",
            "value_type": "ENTERO",
            "general_value": str(getattr(settings, "CITAS_MAX_POR_EXPEDIENTE_DIA", 3)),
            "min_value": Decimal("0"), "max_value": Decimal("20"),
            "allows_center_override": False,
            "legacy_source": "regla legado P-06",
        },
        {
            "key": "portal.max_citas_futuras",
            "description": "Máximo de citas futuras que un paciente puede tener desde el portal (0 = sin tope)",
            "module": "citas",
            "value_type": "ENTERO",
            "general_value": str(getattr(settings, "PORTAL_MAX_CITAS_FUTURAS", 3)),
            "min_value": Decimal("0"), "max_value": Decimal("20"),
            "allows_center_override": False,
            "legacy_source": None,
        },
        {
            "key": "incapacidad.max_dias",
            "description": "Máximo de días de una incapacidad (salvo maternidad)",
            "module": "incapacidad",
            "value_type": "ENTERO",
            "general_value": "60",
            "min_value": Decimal("1"), "max_value": Decimal("365"),
            "allows_center_override": True,
            "legacy_source": None,
        },
        {
            "key": "incapacidad.max_dias_maternidad",
            "description": "Máximo de días de una incapacidad por maternidad",
            "module": "incapacidad",
            "value_type": "ENTERO",
            "general_value": "90",
            "min_value": Decimal("1"), "max_value": Decimal("365"),
            "allows_center_override": True,
            "legacy_source": None,
        },
        {
            "key": "receta.leyenda",
            "description": "Leyenda institucional impresa al pie de la receta",
            "module": "receta",
            "value_type": "TEXTO",
            "general_value": "CUIDA TU PESO, ALIMENTATE SANAMENTE",
            "min_value": None, "max_value": None,
            "allows_center_override": True,
            "legacy_source": "ope_param.ds_mreceta",
        },
    ]


def seed(apps, schema_editor):
    Definicion = apps.get_model("catalogos", "ParametroDefinicion")
    for data in _definitions():
        Definicion.objects.get_or_create(key=data["key"], defaults=data)


def unseed(apps, schema_editor):
    Definicion = apps.get_model("catalogos", "ParametroDefinicion")
    Centro = apps.get_model("catalogos", "ParametroCentro")
    keys = [d["key"] for d in _definitions()]
    Centro.objects.filter(definition__key__in=keys).delete()
    Definicion.objects.filter(key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0042_parametros"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
