from django.db import transaction

from apps.consulta_medica.repositories.clinical_history_repository import ClinicalHistoryRepository

from .consultation_usecase import ensure_doctor_role

# Serializer (camelCase) -> columna del modelo (snake_case).
CLINICAL_HISTORY_FIELD_MAP = {
    "occupationId": "occupation_id",
    "educationLevelId": "education_level_id",
    "maritalStatusId": "marital_status_id",
    "religionId": "religion_id",
    "residenceTypeId": "residence_type_id",
    "phone": "phone",
    "familyHistory": "family_history",
    "currentIllness": "current_illness",
    "systemsReview": "systems_review",
    "headExam": "head_exam",
    "neckExam": "neck_exam",
    "chestExam": "chest_exam",
    "abdomenExam": "abdomen_exam",
    "genitalsExam": "genitals_exam",
    "limbsExam": "limbs_exam",
    "diagnosticManagement": "diagnostic_management",
    "therapeuticManagement": "therapeutic_management",
    "allergies": "allergies",
}

# Campos de texto largo (TextField en el modelo): se auditan como longitud
# (`<campo>Len`), nunca el contenido -- criterio de contenido clinico A3
# (no duplicar el expediente en auditoria_eventos, minimizacion de datos).
_LONG_TEXT_FIELDS = {
    "family_history",
    "current_illness",
    "systems_review",
    "head_exam",
    "neck_exam",
    "chest_exam",
    "abdomen_exam",
    "genitals_exam",
    "limbs_exam",
    "diagnostic_management",
    "therapeutic_management",
    "allergies",
}

_SNAKE_TO_CAMEL = {snake: camel for camel, snake in CLINICAL_HISTORY_FIELD_MAP.items()}


def _clinical_history_field_snapshot(field_values):
    """`field_values`: dict {snake_case_field: valor}. Devuelve dict
    JSON-safe en camelCase, con `<campo>Len` para los de texto largo."""
    snapshot = {}
    for field_name, value in field_values.items():
        camel_key = _SNAKE_TO_CAMEL[field_name]
        if field_name in _LONG_TEXT_FIELDS:
            snapshot[f"{camel_key}Len"] = len(value) if value else None
        else:
            snapshot[camel_key] = value
    return snapshot


def get_clinical_history(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
    return ClinicalHistoryRepository.to_contract(history)


def upsert_clinical_history(
    no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, audit_hook,
):
    ensure_doctor_role(roles, permissions)

    history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)

    model_fields = {
        CLINICAL_HISTORY_FIELD_MAP[key]: value
        for key, value in validated_data.items()
        if key in CLINICAL_HISTORY_FIELD_MAP
    }

    with transaction.atomic():
        # Gotcha A4.4: ClinicalHistoryRepository.update muta la instancia en
        # memoria -- los valores previos se capturan ANTES de llamarlo.
        previous_values = {field_name: getattr(history, field_name) for field_name in model_fields}
        datos_antes = _clinical_history_field_snapshot(previous_values)
        # Replica el mismo criterio de ClinicalHistoryRepository.update para
        # saber si esta llamada va a crear una ClinicalHistoryRevision (solo
        # cuando un campo YA tenia valor y se sobreescribe con otro).
        revision_created = any(
            previous_values[field_name] not in (None, "") and previous_values[field_name] != value
            for field_name, value in model_fields.items()
        )

        history = ClinicalHistoryRepository.update(
            history,
            fields=model_fields,
            updated_by_id=actor_id,
        )

        changed_fields = sorted(
            _SNAKE_TO_CAMEL[field_name]
            for field_name, new_value in model_fields.items()
            if previous_values[field_name] != new_value
        )
        datos_despues = _clinical_history_field_snapshot(model_fields)
        datos_despues["changedFields"] = changed_fields
        datos_despues["revisionCreated"] = revision_created

        audit_hook(
            resource_id=history.id_clinical_history,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            strict=True,
        )

    return ClinicalHistoryRepository.to_contract(history)
