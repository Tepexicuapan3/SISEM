"""Datos iniciales del modulo de autorizaciones. Idempotente por clave.

El disparador COSTO_RECETA no se siembra: exige monto_umbral y
cat_medicamentos todavia no tiene costo (decision A del plan). Se da de
alta desde configuracion cuando se defina.
"""
from django.db import migrations

TIPOS = [
    # clave, nombre, tipo_origen
    ("LAB", "Laboratorio", "PASE_LABORATORIO"),
    ("GAB", "Gabinete", "PASE_GABINETE"),
    ("REC", "Recetas", "RECETA"),
    ("CNO", "Cancelación de nota", "CANCELACION_NOTA"),
]

DISPARADORES = [
    # clave del tipo, clave del disparador
    ("REC", "MEDICAMENTO_ESPECIAL"),
    ("REC", "MEDICAMENTO_CONTROLADO"),
    ("LAB", "ESTUDIO_MARCADO"),
    ("GAB", "ESTUDIO_MARCADO"),
    ("CNO", "CANCELACION_NOTA"),
]

MOTIVOS = [
    # ambito, clave, descripcion, requiere_descripcion_libre
    ("RECHAZO", "NO_JUSTIFICADO", "No está justificado clínicamente", False),
    ("RECHAZO", "ALTERNATIVA_CB", "Existe alternativa en cuadro básico", False),
    ("RECHAZO", "DOC_INCOMPLETA", "Documentación incompleta", False),
    ("RECHAZO", "DUPLICADO", "Solicitud duplicada", False),
    ("RECHAZO", "OTRO", "Otro motivo", True),
    ("SUSPENSION", "LICENCIA", "Licencia o incapacidad", False),
    ("SUSPENSION", "INVESTIGACION", "Investigación administrativa", False),
    ("SUSPENSION", "SOLICITUD_PROPIA", "A solicitud propia", False),
    ("SUSPENSION", "OTRO", "Otro motivo", True),
    ("BAJA", "CAMBIO_ADSCRIPCION", "Cambio de adscripción", False),
    ("BAJA", "TERMINO_DESIGNACION", "Término de la designación", False),
    ("BAJA", "BAJA_LABORAL", "Baja laboral", False),
    ("BAJA", "OTRO", "Otro motivo", True),
    ("CANCELACION", "ORIGEN_CANCELADO", "Se canceló el documento de origen", False),
    ("CANCELACION", "OTRO", "Otro motivo", True),
]


def sembrar(apps, schema_editor):
    TipoAutorizacion = apps.get_model("autorizaciones", "TipoAutorizacion")
    Disparador = apps.get_model("autorizaciones", "Disparador")
    Motivo = apps.get_model("autorizaciones", "Motivo")

    tipos = {}
    for clave, nombre, tipo_origen in TIPOS:
        tipo = TipoAutorizacion.objects.filter(clave=clave, fecha_baja__isnull=True).first()
        if tipo is None:
            tipo = TipoAutorizacion.objects.create(clave=clave, nombre=nombre, tipo_origen=tipo_origen)
        tipos[clave] = tipo

    for clave_tipo, clave in DISPARADORES:
        Disparador.objects.get_or_create(
            tipo_autorizacion=tipos[clave_tipo], clave=clave,
            centro_atencion=None, fecha_baja=None,
        )

    for ambito, clave, descripcion, libre in MOTIVOS:
        Motivo.objects.get_or_create(
            ambito=ambito, clave=clave,
            defaults={"descripcion": descripcion, "requiere_descripcion_libre": libre},
        )


class Migration(migrations.Migration):
    dependencies = [("autorizaciones", "0001_tablas_autorizadores")]

    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
