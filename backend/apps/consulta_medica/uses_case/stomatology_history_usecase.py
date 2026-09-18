from django.db import transaction

from apps.consulta_medica.repositories.stomatology_history_repository import (
    StomatologyHistoryRepository,
)

from .consultation_usecase import ensure_doctor_role

# Serializer (camelCase) -> columna del modelo (snake_case).
STOMATOLOGY_HISTORY_FIELD_MAP = {
    "familyDiabetes": "family_diabetes",
    "familyCancer": "family_cancer",
    "familyHighBloodPressure": "family_high_blood_pressure",
    "familyLowBloodPressure": "family_low_blood_pressure",
    "causeOfDeath": "cause_of_death",
    "personalDiabetes": "personal_diabetes",
    "personalAsthma": "personal_asthma",
    "personalHighBloodPressure": "personal_high_blood_pressure",
    "personalLowBloodPressure": "personal_low_blood_pressure",
    "personalHepatitis": "personal_hepatitis",
    "personalHiv": "personal_hiv",
    "personalSmoking": "personal_smoking",
    "personalAlcoholism": "personal_alcoholism",
    "personalSubstanceAbuse": "personal_substance_abuse",
    "habits": "habits",
    "diet": "diet",
    "surgicalHistory": "surgical_history",
    "traumaticHistory": "traumatic_history",
    "allergyMedications": "allergy_medications",
    "allergyDentalMaterial": "allergy_dental_material",
    "allergyAnesthesia": "allergy_anesthesia",
    "allergyFood": "allergy_food",
    "allergyEnvironment": "allergy_environment",
    "allergyOther": "allergy_other",
    "currentIllnessHistory": "current_illness_history",
}

# Campos de texto largo (TextField en el modelo): se auditan como longitud
# (`<campo>Len`), nunca el contenido -- mismo criterio A3 que ClinicalHistory.
# `cause_of_death` es CharField(255) corto -- se audita tal cual (booleanos y
# el resto de campos cortos van sin transformar).
_LONG_TEXT_FIELDS = {
    "habits",
    "diet",
    "surgical_history",
    "traumatic_history",
    "allergy_medications",
    "allergy_dental_material",
    "allergy_anesthesia",
    "allergy_food",
    "allergy_environment",
    "allergy_other",
    "current_illness_history",
}

_SNAKE_TO_CAMEL = {snake: camel for camel, snake in STOMATOLOGY_HISTORY_FIELD_MAP.items()}


def _stomatology_history_field_snapshot(field_values):
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


def get_stomatology_history(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    history, _ = StomatologyHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
    return StomatologyHistoryRepository.to_contract(history)


def upsert_stomatology_history(
    no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, audit_hook,
):
    ensure_doctor_role(roles, permissions)

    history, _ = StomatologyHistoryRepository.get_or_create_for_patient(no_exp, pk_num)

    model_fields = {
        STOMATOLOGY_HISTORY_FIELD_MAP[key]: value
        for key, value in validated_data.items()
        if key in STOMATOLOGY_HISTORY_FIELD_MAP
    }

    with transaction.atomic():
        # Gotcha A4.4: StomatologyHistoryRepository.update muta la instancia
        # en memoria -- los valores previos se capturan ANTES de llamarlo.
        previous_values = {field_name: getattr(history, field_name) for field_name in model_fields}
        datos_antes = _stomatology_history_field_snapshot(previous_values)

        history = StomatologyHistoryRepository.update(
            history,
            fields=model_fields,
            updated_by_id=actor_id,
        )

        changed_fields = sorted(
            _SNAKE_TO_CAMEL[field_name]
            for field_name, new_value in model_fields.items()
            if previous_values[field_name] != new_value
        )
        datos_despues = _stomatology_history_field_snapshot(model_fields)
        datos_despues["changedFields"] = changed_fields

        audit_hook(
            resource_id=history.id_stomatology_history,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            strict=True,
        )

    return StomatologyHistoryRepository.to_contract(history)
