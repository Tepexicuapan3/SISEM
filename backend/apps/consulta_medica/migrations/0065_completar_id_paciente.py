"""
Plan contraer la llave vieja, C6: antes de volver obligatorio id_paciente en
las tablas de atencion, se completa donde falte con la misma logica del
comando vincular_id_paciente (resuelve o abre el registro por su llave). En
el servidor el SELECT del 2026-10-27 dio 0 filas sin id_paciente en las
tablas operativas; esto cubre cualquier fila creada despues o en las tablas
clinicas que no estaban en ese conteo.

Usa los modelos actuales (no los historicos) a proposito: la logica de
resolucion vive en patient_link_service. Va separada del NOT NULL por el
"pending trigger events" de Postgres (mismo motivo que 0057/0058).
"""
from django.db import migrations


def completar(apps, schema_editor):
    from apps.consulta_medica.services.patient_link_service import link_existing

    link_existing(dry_run=False, create_missing=True)


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0064_llave_vieja_opcional"),
        ("recepcion", "0029_llave_vieja_opcional"),
        ("somatometria", "0011_llave_vieja_opcional"),
        ("cirugias", "0003_llave_vieja_opcional"),
        ("hospitalizacion", "0003_llave_vieja_opcional"),
        ("ambulancias", "0003_llave_vieja_opcional"),
        ("pases", "0004_llave_vieja_opcional"),
        ("contratos_oxigeno", "0009_llave_vieja_opcional"),
        ("padrones", "0002_llave_vieja_opcional"),
        ("portal_citas", "0002_id_paciente_operativo"),
    ]

    operations = [
        migrations.RunPython(completar, migrations.RunPython.noop),
    ]
