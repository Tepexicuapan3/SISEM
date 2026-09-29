"""
Migracion de DATOS del Nucleo del paciente (documento "Historia Clinica
Unificada", 5.1), para que quede tal cual el modelo del documento:

  ClinicalHistory (datos de la persona)  -> Patient (PACIENTE), 1:1
  ClinicalHistoryRevision                -> PatientRevision
  ClinicalHistory.created_at             -> opened_on (HISTORIA_CLINICA.fe_apertura)
  HistoricalNote                         -> FK a su HistoricalNote.clinical_history
  Allergy.category                       -> allergy_type (CAT_TIPO_ALERGIA 1/2/3/4/5/9)
  Allergy.severity mild/moderate/severe  -> L/M/G
  Allergy.status active/resolved/error   -> A/R/E
  PersonalHistory.status active/resolved -> A/R
  Habit.status current/former            -> A/E
  HistoricalNote.origin legacy/revision  -> M (migrado) / V (version anterior)

La 0033 borra lo que aqui se movio. Todo dentro de la transaccion de la
migracion (Postgres): o se aplica completo, o nada.
"""
from django.db import migrations
from django.utils import timezone

CATEGORY_TO_TYPE = {
    "medication": 1, "anesthesia": 2, "dental_material": 3,
    "environmental": 4, "food": 5, "other": 9,
}
SEVERITY = {"mild": "L", "moderate": "M", "severe": "G"}
ALLERGY_STATUS = {"active": "A", "resolved": "R", "entered_in_error": "E"}
PERSONAL_STATUS = {"active": "A", "resolved": "R"}
HABIT_STATUS = {"current": "A", "former": "E"}
NOTE_ORIGIN = {"legacy_text": "M", "revision": "V"}

PATIENT_FIELDS = (
    "curp", "sex", "occupation_id", "education_level_id", "marital_status_id",
    "religion_id", "residence_type_id", "phone",
)


def _remap(model, field, mapping):
    for old, new in mapping.items():
        model.objects.filter(**{field: old}).update(**{field: new})


def forwards(apps, schema_editor):
    ClinicalHistory = apps.get_model("consulta_medica", "ClinicalHistory")
    ClinicalHistoryRevision = apps.get_model("consulta_medica", "ClinicalHistoryRevision")
    Patient = apps.get_model("consulta_medica", "Patient")
    PatientRevision = apps.get_model("consulta_medica", "PatientRevision")
    HistoricalNote = apps.get_model("consulta_medica", "HistoricalNote")
    Allergy = apps.get_model("consulta_medica", "Allergy")
    AllergyRevision = apps.get_model("consulta_medica", "AllergyRevision")
    PersonalHistory = apps.get_model("consulta_medica", "PersonalHistory")
    Habit = apps.get_model("consulta_medica", "Habit")

    # 1. PACIENTE 1:1 con cada historia existente.
    for history in ClinicalHistory.objects.all().iterator():
        patient = Patient.objects.create(
            no_exp=history.no_exp, pk_num=history.pk_num,
            created_by_id=history.created_by_id, updated_by_id=history.updated_by_id,
            **{field: getattr(history, field) for field in PATIENT_FIELDS},
        )
        history.patient_id = patient.pk
        history.opened_on = timezone.localtime(history.created_at).date() if history.created_at else None
        history.save(update_fields=["patient", "opened_on"])

    # 2. Versiones anteriores de la ficha.
    for revision in ClinicalHistoryRevision.objects.select_related("history").iterator():
        new = PatientRevision.objects.create(
            patient_id=revision.history.patient_id,
            changed_by_id=revision.changed_by_id,
            **{f"previous_{field}": getattr(revision, f"previous_{field}") for field in PATIENT_FIELDS},
        )
        PatientRevision.objects.filter(pk=new.pk).update(changed_at=revision.changed_at)

    # 3. NOTA_HISTORICA -> HISTORIA_CLINICA (se crea la cabecera si faltaba).
    patients_without_history = (
        HistoricalNote.objects.filter(clinical_history__isnull=True)
        .values_list("no_exp", "pk_num").distinct()
    )
    for no_exp, pk_num in patients_without_history:
        history = ClinicalHistory.objects.filter(no_exp=no_exp, pk_num=pk_num).first()
        if history is None:
            patient, _ = Patient.objects.get_or_create(no_exp=no_exp, pk_num=pk_num)
            history = ClinicalHistory.objects.create(
                no_exp=no_exp, pk_num=pk_num, patient_id=patient.pk, opened_on=timezone.localdate(),
            )
        HistoricalNote.objects.filter(no_exp=no_exp, pk_num=pk_num).update(clinical_history=history)
    _remap(HistoricalNote, "origin", NOTE_ORIGIN)

    # 4. ALERGIA: tipo por catalogo y codigos del documento.
    for category, type_id in CATEGORY_TO_TYPE.items():
        Allergy.objects.filter(category=category).update(allergy_type_id=type_id)
        AllergyRevision.objects.filter(previous_category=category).update(previous_allergy_type_id=type_id)
    _remap(Allergy, "severity", SEVERITY)
    _remap(AllergyRevision, "previous_severity", SEVERITY)
    _remap(Allergy, "status", ALLERGY_STATUS)

    # 5. Estados de antecedentes y habitos.
    _remap(PersonalHistory, "status", PERSONAL_STATUS)
    _remap(Habit, "status", HABIT_STATUS)


class Migration(migrations.Migration):
    dependencies = [
        ("consulta_medica", "0031_paciente_esquema"),
        ("catalogos", "0033_cat_tipo_alergia"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
