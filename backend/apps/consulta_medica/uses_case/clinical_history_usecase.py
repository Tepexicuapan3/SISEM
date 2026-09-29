"""
Nucleo del paciente (documento "Historia Clinica Unificada", 5.1):
PACIENTE (ficha: identidad + datos sociodemograficos, editable y
versionada) e HISTORIA_CLINICA (cabecera unica: apertura, solo lectura).
"""
from django.db import transaction

from apps.consulta_medica.repositories.clinical_history_repository import (
    ClinicalHistoryRepository,
    PatientRepository,
)

from .consultation_usecase import ensure_doctor_role

# Serializer (camelCase) -> columna de PACIENTE (snake_case).
PATIENT_FIELD_MAP = {
    "curp": "curp",
    "sex": "sex",
    "occupationId": "occupation_id",
    "educationLevelId": "education_level_id",
    "maritalStatusId": "marital_status_id",
    "religionId": "religion_id",
    "residenceTypeId": "residence_type_id",
    "phone": "phone",
}

_SNAKE_TO_CAMEL = {snake: camel for camel, snake in PATIENT_FIELD_MAP.items()}


def _snapshot(field_values):
    return {_SNAKE_TO_CAMEL[field_name]: value for field_name, value in field_values.items()}


def get_clinical_history(no_exp, pk_num, roles, permissions=None):
    """HISTORIA_CLINICA: se abre (con su PACIENTE) la primera vez que se consulta."""
    ensure_doctor_role(roles, permissions)
    history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
    return ClinicalHistoryRepository.to_contract(history)


def get_patient_profile(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
    return PatientRepository.to_contract(history.patient)


def update_patient_profile(
    no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, audit_hook,
):
    ensure_doctor_role(roles, permissions)
    history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
    patient = history.patient

    model_fields = {
        PATIENT_FIELD_MAP[key]: value
        for key, value in validated_data.items()
        if key in PATIENT_FIELD_MAP
    }

    with transaction.atomic():
        # PatientRepository.update muta la instancia: previos ANTES de llamarlo.
        previous_values = {field_name: getattr(patient, field_name) for field_name in model_fields}
        revision_created = any(
            previous_values[field_name] not in (None, "") and previous_values[field_name] != value
            for field_name, value in model_fields.items()
        )

        patient = PatientRepository.update(patient, fields=model_fields, updated_by_id=actor_id)

        datos_despues = _snapshot(model_fields)
        datos_despues["changedFields"] = sorted(
            _SNAKE_TO_CAMEL[field_name]
            for field_name, new_value in model_fields.items()
            if previous_values[field_name] != new_value
        )
        datos_despues["revisionCreated"] = revision_created

        audit_hook(
            resource_id=patient.id_patient,
            datos_antes=_snapshot(previous_values),
            datos_despues=datos_despues,
            strict=True,
        )

    return PatientRepository.to_contract(patient)
