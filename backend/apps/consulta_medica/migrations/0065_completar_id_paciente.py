"""
Plan contraer la llave vieja, C6: antes de volver obligatorio id_paciente en
las tablas de atencion, se completa donde falte, resolviendo (o abriendo) el
registro de cns_paciente por la llave de la fila. En el servidor el SELECT del
2026-10-27 dio 0 filas sin id_paciente en las tablas operativas; esto cubre
cualquier fila creada despues o en las tablas clinicas que no estaban en ese
conteo.

Usa los modelos HISTORICOS: en este punto de la historia las tablas todavia
tienen no_exp/pk_num (C7 las borra despues), asi que funciona igual en una
base nueva, en los tests y en un servidor atrasado. Va separada del NOT NULL
por el "pending trigger events" de Postgres (mismo motivo que 0057/0058).
"""
from django.db import migrations
from django.db.models import Q

# tabla -> campo con el expediente
TABLAS = {
    "recepcion.Visit": "no_exp", "recepcion.CitaMedica": "no_exp",
    "somatometria.VisitVitalSigns": "no_exp", "somatometria.PatientLatestVitals": "no_exp",
    "consulta_medica.Allergy": "no_exp", "consulta_medica.MedicalLeave": "no_exp",
    "consulta_medica.StudyResult": "no_exp", "consulta_medica.StomatologyHistory": "no_exp",
    "consulta_medica.Odontogram": "no_exp", "consulta_medica.ClinicalHistory": "no_exp",
    "consulta_medica.PersonalHistory": "no_exp", "consulta_medica.FamilyHistory": "no_exp",
    "consulta_medica.SurgicalHistory": "no_exp", "consulta_medica.Habit": "no_exp",
    "consulta_medica.DentalTreatment": "no_exp",
    "cirugias.SurgerySchedule": "no_exp", "hospitalizacion.HospitalAdmission": "no_exp",
    "ambulancias.AmbulanceRequest": "no_exp", "pases.Referral": "no_exp",
    "contratos_oxigeno.ContratoOxigeno": "expediente",
    "padrones.ChronicEnrollment": "no_exp", "padrones.DisabilityEnrollment": "no_exp",
}


def _normalizar(no_exp):
    texto = str(no_exp).strip()
    return str(int(texto)) if texto.isdigit() else texto


def completar(apps, schema_editor):
    Patient = apps.get_model("consulta_medica", "Patient")
    Person = apps.get_model("consulta_medica", "Person")

    def registro(no_exp, pk_num):
        no_exp = _normalizar(no_exp)
        paciente = Patient.objects.filter(no_exp=no_exp, pk_num=pk_num).first()
        if paciente is None:
            paciente = Patient.objects.filter(
                Q(legacy_family_code=pk_num) | Q(provisional_code=pk_num), no_exp=no_exp, pk_num__isnull=True,
            ).first()
        if paciente is None:
            paciente = Patient.objects.create(no_exp=no_exp, pk_num=pk_num, person=Person.objects.create())
        return paciente

    for label, campo in TABLAS.items():
        modelo = apps.get_model(*label.split("."))
        if not {campo, "pk_num"} <= {f.name for f in modelo._meta.concrete_fields}:
            continue  # la tabla ya no tiene la llave (C7 aplicado antes, p. ej. en tests)
        pendientes = modelo.objects.filter(patient__isnull=True, pk_num__isnull=False).exclude(**{campo: None})
        for no_exp, pk_num in list(pendientes.values_list(campo, "pk_num").distinct()):
            if no_exp:
                pendientes.filter(**{campo: no_exp}, pk_num=pk_num).update(patient=registro(no_exp, pk_num))


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
