"""
Nucleo del paciente (documento "Historia Clinica Unificada", 5.1):
PACIENTE (ficha: identidad + datos sociodemograficos, editable y
versionada) e HISTORIA_CLINICA (cabecera unica: apertura, solo lectura).
"""
from django.db import transaction

from apps.consulta_medica.models import ChangeLog, Patient
from apps.consulta_medica.repositories.clinical_history_repository import (
    ClinicalHistoryRepository,
    PatientRepository,
)
from apps.consulta_medica.services.change_log_service import build_key, record_change
from apps.consulta_medica.services.curp_rules import curp_mismatches
from apps.recepcion.services.errors import VisitDomainError

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


def _identity_rules(patient, model_fields):
    """
    Reglas de CURP del 5.1. Devuelve los campos derivados que hay que guardar
    ademas de los editados (hoy, solo curp_source). Lanza VisitDomainError si
    la edicion no se permite.
    """
    derived = {}
    new_curp = model_fields.get("curp", patient.curp)
    new_sex = model_fields.get("sex", patient.sex)

    if "curp" in model_fields and new_curp != patient.curp:
        if patient.curp_source == Patient.CurpSource.SERMED:
            raise VisitDomainError(
                "CURP_FROM_SERMED",
                "La CURP de este titular viene de Capital Humano (SERMED) y no se puede editar en SIRES.",
                409,
                details={"curp": ["Solo Capital Humano puede corregir esta CURP."]},
            )
        if new_curp:
            owner = Patient.objects.filter(curp=new_curp).exclude(pk=patient.pk).first()
            if owner:
                raise VisitDomainError(
                    "CURP_ALREADY_REGISTERED",
                    f"Esta CURP ya pertenece al expediente {owner.no_exp}. "
                    "Puede ser la misma persona con dos expedientes: avisar para revisarlo.",
                    409,
                    details={"curp": ["CURP registrada en otro paciente."],
                             "noExp": owner.no_exp, "pkNum": owner.pk_num},
                )
        derived["curp_source"] = Patient.CurpSource.CAPTURED if new_curp else None

    if new_curp and ("curp" in model_fields or "sex" in model_fields):
        mismatches = curp_mismatches(new_curp, birth_date=patient.birth_date, sex=new_sex)
        if mismatches:
            raise VisitDomainError(
                "VALIDATION_ERROR",
                "La CURP no coincide con los datos del paciente.",
                422,
                details={field: [message] for field, message in mismatches.items()},
            )
    return derived


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

    derived_fields = _identity_rules(patient, model_fields)

    with transaction.atomic():
        # PatientRepository.update muta la instancia: previos ANTES de llamarlo.
        previous_values = {field_name: getattr(patient, field_name) for field_name in model_fields}
        previous_derived = {field_name: getattr(patient, field_name) for field_name in derived_fields}
        revision_created = any(
            previous_values[field_name] not in (None, "") and previous_values[field_name] != value
            for field_name, value in model_fields.items()
        )

        patient = PatientRepository.update(
            patient, fields={**model_fields, **derived_fields}, updated_by_id=actor_id,
        )

        # Bitacora de cambios (seccion 6): rellenar un dato vacio es CAPTURA;
        # sobrescribir un valor existente es CORRECCION.
        if actor_id is not None:
            record_change(
                table="cns_paciente",
                key=build_key("id_paciente", patient.id_patient),
                action=ChangeLog.Action.UPDATE,
                reason=ChangeLog.Reason.CORRECTION if revision_created else ChangeLog.Reason.CAPTURE,
                user=actor_id,
                previous={**previous_values, **previous_derived},
                new={**model_fields, **derived_fields},
            )

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
