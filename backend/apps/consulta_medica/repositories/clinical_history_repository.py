from django.db import transaction
from django.utils import timezone

from apps.consulta_medica.models import ClinicalHistory, Patient, PatientRevision

# Campos editables de PACIENTE -- mismo set que PATIENT_FIELD_MAP en
# clinical_history_usecase.py. Se usa para saber que "previous_<campo>"
# snapshotear en PatientRevision.
_VERSIONED_FIELDS = (
    "curp",
    "sex",
    "occupation_id",
    "education_level_id",
    "marital_status_id",
    "religion_id",
    "residence_type_id",
    "phone",
)


class PatientRepository:
    """PACIENTE: datos de la persona (1 por no_exp + tp_paciente)."""

    @staticmethod
    def get_or_create(no_exp, pk_num):
        return Patient.objects.get_or_create(no_exp=no_exp, pk_num=pk_num)

    @staticmethod
    def update(patient, *, fields, updated_by_id=None):
        # Captura incremental: rellenar un campo vacio por primera vez no es
        # alterar un dato -- solo versiona cuando YA habia un valor concreto
        # y se sobreescribe con otro (NOM-024: nada se pisa sin rastro).
        changed = any(
            getattr(patient, field_name) not in (None, "") and getattr(patient, field_name) != value
            for field_name, value in fields.items()
        )
        if changed:
            PatientRevision.objects.create(
                patient=patient,
                changed_by_id=updated_by_id,
                **{f"previous_{field_name}": getattr(patient, field_name) for field_name in _VERSIONED_FIELDS},
            )
        for field_name, value in fields.items():
            setattr(patient, field_name, value)
        patient.updated_by_id = updated_by_id
        patient.save()
        return patient

    @staticmethod
    def to_contract(patient):
        return {
            "id": patient.id_patient,
            "noExp": patient.no_exp,
            "pkNum": patient.pk_num,
            "curp": patient.curp,
            "sex": patient.sex,
            "occupationId": patient.occupation_id,
            "educationLevelId": patient.education_level_id,
            "maritalStatusId": patient.marital_status_id,
            "religionId": patient.religion_id,
            "residenceTypeId": patient.residence_type_id,
            "phone": patient.phone,
            "createdAt": patient.created_at,
            "updatedAt": patient.updated_at,
        }


class ClinicalHistoryRepository:
    """HISTORIA_CLINICA: cabecera unica por paciente, 1:1 con PACIENTE."""

    @staticmethod
    def get_or_create_for_patient(no_exp, pk_num, *, opened_on=None, clinic_code=None,
                                  doctor_code=None, created_by_id=None):
        with transaction.atomic():
            patient, _ = PatientRepository.get_or_create(no_exp, pk_num)
            history, created = ClinicalHistory.objects.get_or_create(
                no_exp=no_exp,
                pk_num=pk_num,
                defaults={
                    "patient": patient,
                    "opened_on": opened_on or timezone.localdate(),
                    "opening_clinic_code": clinic_code,
                    "opening_doctor_code": doctor_code,
                    "created_by_id": created_by_id,
                },
            )
        return history, created

    @staticmethod
    def to_contract(history):
        return {
            "id": history.id_clinical_history,
            "noExp": history.no_exp,
            "pkNum": history.pk_num,
            "patientId": history.patient_id,
            "openedOn": history.opened_on.isoformat() if history.opened_on else None,
            "openingClinicCode": history.opening_clinic_code,
            "openingDoctorCode": history.opening_doctor_code,
            "isActive": history.is_active,
            "createdAt": history.created_at,
        }
