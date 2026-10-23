"""
Plan identidad del paciente, Fase 2: el sexo pasa de la convencion de la CURP
(H = Hombre, M = Mujer) a la de SERMED (M = Masculino, F = Femenino); X se
mantiene. Decidido con el usuario el 2026-10-22.

Convierte cns_paciente.sexo y cns_paciente_revision.sexo_anterior en un solo
UPDATE por tabla (CASE sobre el valor anterior: ningun valor se convierte dos
veces).

cns_bitacora_cambios es inmutable (trigger): sus filas anteriores conservan
H/M con el significado viejo. La FECHA DE CORTE es el momento en que se
aplico esta migracion, que Django ya registra:
    SELECT applied FROM django_migrations
    WHERE app = 'consulta_medica' AND name = '0056_sexo_convencion_sermed';
Antes de esa fecha, en la bitacora, H = Hombre y M = Mujer; despues,
M = Masculino y F = Femenino.
"""
from django.db import migrations, models
from django.db.models import Case, Value, When

A_SERMED = {"H": "M", "M": "F"}
A_CURP = {"M": "H", "F": "M"}


def _convertir(Modelo, campo, mapa):
    casos = [When(**{campo: viejo}, then=Value(nuevo)) for viejo, nuevo in mapa.items()]
    Modelo.objects.filter(**{f"{campo}__in": list(mapa)}).update(
        **{campo: Case(*casos, output_field=models.CharField())}
    )


def a_sermed(apps, schema_editor):
    _convertir(apps.get_model("consulta_medica", "Patient"), "sex", A_SERMED)
    _convertir(apps.get_model("consulta_medica", "PatientRevision"), "previous_sex", A_SERMED)


def a_curp(apps, schema_editor):
    _convertir(apps.get_model("consulta_medica", "Patient"), "sex", A_CURP)
    _convertir(apps.get_model("consulta_medica", "PatientRevision"), "previous_sex", A_CURP)


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0055_bitacora_cambios_inmutable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="sex",
            field=models.CharField(
                blank=True, choices=[("M", "Masculino"), ("F", "Femenino"), ("X", "No binario")],
                db_column="sexo", max_length=1, null=True,
            ),
        ),
        migrations.RunPython(a_sermed, a_curp),
    ]
