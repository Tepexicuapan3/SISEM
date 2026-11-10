"""Pie de la receta: separa leyenda y mensaje de salud.

0043 sembro "CUIDA TU PESO, ALIMENTATE SANAMENTE" (ope_param.ds_mreceta) como
receta.leyenda, pero ese texto es el mensaje de salud, y receta.mensaje_salud
no tenia definicion: la receta imprimia "Nota: CUIDA TU PESO..." y el mensaje
quedaba vacio. La leyenda es la nota de surtido de la receta del legado.

Solo corrige la leyenda si conserva el valor sembrado (un admin pudo haberla
cambiado). El mensaje de salud es idempotente por clave, igual que 0043.
"""
from django.db import migrations

VALOR_SEMBRADO = "CUIDA TU PESO, ALIMENTATE SANAMENTE"

LEYENDA = (
    "ESTA RECETA SERÁ SURTIDA EL MISMO DÍA DE SU EMISIÓN EN CASO DE MEDICAMENTO FALTANTE "
    "SE SURTIRAN EN LAS PRÓXIMAS 72 HORAS MEDIANTE RECETA FALTANTE "
    "ESTE DOCUMENTO NO PIERDE VIGENCIA."
)

MENSAJE_SALUD = {
    "key": "receta.mensaje_salud",
    "description": "Mensaje de salud al paciente impreso al pie de la receta",
    "module": "receta",
    "value_type": "TEXTO",
    "general_value": VALOR_SEMBRADO,
    "min_value": None, "max_value": None,
    "allows_center_override": True,
    "legacy_source": "ope_param.ds_mreceta",
}


def seed(apps, schema_editor):
    Definicion = apps.get_model("catalogos", "ParametroDefinicion")
    Definicion.objects.filter(key="receta.leyenda", general_value=VALOR_SEMBRADO).update(
        general_value=LEYENDA, legacy_source="receta del legado (nota de surtido)",
    )
    Definicion.objects.get_or_create(key=MENSAJE_SALUD["key"], defaults=MENSAJE_SALUD)


def unseed(apps, schema_editor):
    Definicion = apps.get_model("catalogos", "ParametroDefinicion")
    Centro = apps.get_model("catalogos", "ParametroCentro")
    Centro.objects.filter(definition__key=MENSAJE_SALUD["key"]).delete()
    Definicion.objects.filter(key=MENSAJE_SALUD["key"]).delete()
    Definicion.objects.filter(key="receta.leyenda", general_value=LEYENDA).update(
        general_value=VALOR_SEMBRADO, legacy_source="ope_param.ds_mreceta",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0045_parametro_anticipacion_checkin"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
