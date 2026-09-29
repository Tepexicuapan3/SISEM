"""
Datos para la estructura exacta del documento en estomatologia y alergias:

  HC_ESTOMATOLOGIA.id_historia  -> StomatologyHistory.clinical_history
  ODONTOGRAMA.id_hc_estoma      -> Odontogram.stomatology_history
  ODONTOGRAMA.indice_cpod       -> Odontogram.dmft_total (C + P + O)
  ALERGIA.cd_servicio_origen    -> Allergy.service_origin_code
                                   (cat_servicios del legado: 1 Medicina
                                   General, 5 Odontologia)

Si un paciente con seccion dental u odontograma no tiene HISTORIA_CLINICA
(ni PACIENTE), se crean: en el documento la seccion dental cuelga de la
historia unica del paciente.
"""
from django.db import migrations
from django.utils import timezone

SERVICE_CODE = {"general": 1, "stomatology": 5}


def forwards(apps, schema_editor):
    Patient = apps.get_model("consulta_medica", "Patient")
    ClinicalHistory = apps.get_model("consulta_medica", "ClinicalHistory")
    StomatologyHistory = apps.get_model("consulta_medica", "StomatologyHistory")
    Odontogram = apps.get_model("consulta_medica", "Odontogram")
    Allergy = apps.get_model("consulta_medica", "Allergy")

    def history_for(no_exp, pk_num):
        history = ClinicalHistory.objects.filter(no_exp=no_exp, pk_num=pk_num).first()
        if history is None:
            patient, _ = Patient.objects.get_or_create(no_exp=no_exp, pk_num=pk_num)
            history = ClinicalHistory.objects.create(
                no_exp=no_exp, pk_num=pk_num, patient_id=patient.pk, opened_on=timezone.localdate(),
            )
        return history

    for section in StomatologyHistory.objects.filter(clinical_history__isnull=True).iterator():
        section.clinical_history_id = history_for(section.no_exp, section.pk_num).pk
        section.save(update_fields=["clinical_history"])

    for odontogram in Odontogram.objects.filter(stomatology_history__isnull=True).iterator():
        section = StomatologyHistory.objects.filter(no_exp=odontogram.no_exp, pk_num=odontogram.pk_num).first()
        if section is None:
            section = StomatologyHistory.objects.create(
                no_exp=odontogram.no_exp, pk_num=odontogram.pk_num,
                clinical_history_id=history_for(odontogram.no_exp, odontogram.pk_num).pk,
            )
        odontogram.stomatology_history_id = section.pk
        odontogram.dmft_total = odontogram.dmft_decayed + odontogram.dmft_missing + odontogram.dmft_filled
        odontogram.save(update_fields=["stomatology_history", "dmft_total"])

    for source, code in SERVICE_CODE.items():
        Allergy.objects.filter(source=source).update(service_origin_code=code)


class Migration(migrations.Migration):
    dependencies = [
        ("consulta_medica", "0034_documento_estructura_esquema"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
