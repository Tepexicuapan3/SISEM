"""
Plan identidad del paciente: los recien nacidos provisionales ya registrados
pasan su llave de cd_familiar a cd_provisional, y su identificador CD_FAMILIAR
se da de baja (queda como evidencia) a cambio de uno PROVISIONAL. Cada cambio
queda en cns_bitacora_cambios con motivo CORRECCION, como lo haria
patient_identifier_service (aqui no se puede importar: modelos historicos).
"""
from django.db import migrations

MOTIVO = "CORRECCION"
USUARIO = "MIGRACION"
TABLA_ID = "cns_identificador_paciente"


def mover(apps, schema_editor):
    Patient = apps.get_model("consulta_medica", "Patient")
    PatientIdentifier = apps.get_model("consulta_medica", "PatientIdentifier")
    ChangeLog = apps.get_model("consulta_medica", "ChangeLog")

    pacientes = Patient.objects.filter(provisional__isnull=False, legacy_family_code__isnull=False)
    for paciente in pacientes:
        codigo = paciente.legacy_family_code
        paciente.provisional_code, paciente.legacy_family_code = codigo, None
        paciente.save(update_fields=["provisional_code", "legacy_family_code"])
        ChangeLog.objects.create(
            table="cns_paciente", key=f"id_paciente|{paciente.pk}", action="M", reason=MOTIVO, user=USUARIO,
            previous_value={"cd_familiar": codigo, "cd_provisional": None},
            new_value={"cd_familiar": None, "cd_provisional": codigo},
        )
        for anterior in PatientIdentifier.objects.filter(
            patient=paciente, id_type="CD_FAMILIAR", value=str(codigo), status="A",
        ):
            anterior.status, anterior.updated_by = "B", USUARIO
            anterior.save(update_fields=["status", "updated_by", "updated_at"])
            ChangeLog.objects.create(
                table=TABLA_ID, key=f"CD_FAMILIAR|{codigo}", action="B", reason=MOTIVO, user=USUARIO,
                previous_value={"id_paciente": paciente.pk, "sw_status": "A"},
            )
        if not PatientIdentifier.objects.filter(id_type="PROVISIONAL", value=str(codigo), status="A").exists():
            PatientIdentifier.objects.create(
                patient=paciente, id_type="PROVISIONAL", value=str(codigo), created_by=USUARIO,
            )
            ChangeLog.objects.create(
                table=TABLA_ID, key=f"PROVISIONAL|{codigo}", action="A", reason=MOTIVO, user=USUARIO,
                new_value={"id_paciente": paciente.pk},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0061_cd_provisional"),
    ]

    operations = [
        migrations.RunPython(mover, migrations.RunPython.noop),
    ]
