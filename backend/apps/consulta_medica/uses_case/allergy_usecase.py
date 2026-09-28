from django.db import transaction

from apps.catalogos.models import Medicamentos
from apps.consulta_medica.repositories.allergy_repository import AllergyRepository
from apps.recepcion.services.errors import VisitDomainError

from .consultation_usecase import ensure_doctor_role

# Serializer (camelCase) -> columna del modelo (snake_case). Mismo criterio
# que CLINICAL_HISTORY_FIELD_MAP en clinical_history_usecase.py.
ALLERGY_FIELD_MAP = {
    "category": "category",
    "substance": "substance",
    "medicationId": "medication_id",
    "severity": "severity",
    "reaction": "reaction",
}

_SNAKE_TO_CAMEL = {snake: camel for camel, snake in ALLERGY_FIELD_MAP.items()}


def _allergy_field_snapshot(field_values):
    """`field_values`: dict {snake_case_field: valor}. Devuelve dict
    JSON-safe en camelCase -- `reaction` es el unico TextField libre, se
    audita como longitud (criterio A3, igual que ClinicalHistory)."""
    snapshot = {}
    for field_name, value in field_values.items():
        camel_key = _SNAKE_TO_CAMEL[field_name]
        if field_name == "reaction":
            snapshot["reactionLen"] = len(value) if value else None
        else:
            snapshot[camel_key] = value
    return snapshot


def list_allergies(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    allergies = AllergyRepository.list_for_patient(no_exp, pk_num)
    return {"items": [AllergyRepository.to_contract(allergy) for allergy in allergies]}


def _resolve_medication_id(medication_id):
    """Valida que el medicamento exista y este activo -- mismo criterio que
    `add_prescription_item`. `None` (sin medicamento asociado) es valido:
    no toda alergia a un medicamento tiene que estar ligada al catalogo."""
    if medication_id is None:
        return None
    if not Medicamentos.objects.filter(pk=medication_id, is_active=True).exists():
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"medicationId": ["El medicamento no existe o no esta activo."]},
        )
    return medication_id


def create_allergy(
    no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, source, audit_hook,
):
    ensure_doctor_role(roles, permissions)

    medication_id = _resolve_medication_id(validated_data.get("medicationId"))

    with transaction.atomic():
        allergy = AllergyRepository.create(
            no_exp=no_exp,
            pk_num=pk_num,
            category=validated_data["category"],
            substance=validated_data["substance"],
            medication_id=medication_id,
            severity=validated_data["severity"],
            reaction=validated_data.get("reaction"),
            source=source,
            created_by_id=actor_id,
        )

        audit_hook(
            resource_id=allergy.id_allergy,
            datos_antes=None,
            datos_despues=_allergy_field_snapshot(
                {
                    "category": allergy.category,
                    "substance": allergy.substance,
                    "medication_id": allergy.medication_id,
                    "severity": allergy.severity,
                    "reaction": allergy.reaction,
                }
            ),
            strict=True,
        )

    return AllergyRepository.to_contract(allergy)


def update_allergy(
    no_exp, pk_num, allergy_id, roles, validated_data, actor_id, permissions=None, *, audit_hook,
):
    ensure_doctor_role(roles, permissions)

    allergy = AllergyRepository.get_active_by_id(allergy_id, no_exp, pk_num)
    if allergy is None:
        raise VisitDomainError("ALLERGY_NOT_FOUND", "Alergia no encontrada.", 404)

    model_fields = {
        ALLERGY_FIELD_MAP[key]: value
        for key, value in validated_data.items()
        if key in ALLERGY_FIELD_MAP
    }
    if "medication_id" in model_fields:
        model_fields["medication_id"] = _resolve_medication_id(model_fields["medication_id"])

    with transaction.atomic():
        # Gotcha A4.4 (mismo que ClinicalHistoryRepository): update() muta
        # la instancia en memoria -- los valores previos se capturan ANTES.
        previous_values = {field_name: getattr(allergy, field_name) for field_name in model_fields}
        datos_antes = _allergy_field_snapshot(previous_values)

        allergy = AllergyRepository.update(allergy, fields=model_fields, updated_by_id=actor_id)

        datos_despues = _allergy_field_snapshot(model_fields)
        datos_despues["changedFields"] = sorted(
            _SNAKE_TO_CAMEL[field_name]
            for field_name, new_value in model_fields.items()
            if previous_values[field_name] != new_value
        )

        audit_hook(
            resource_id=allergy.id_allergy,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            strict=True,
        )

    return AllergyRepository.to_contract(allergy)


def deactivate_allergy(no_exp, pk_num, allergy_id, roles, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)

    allergy = AllergyRepository.get_active_by_id(allergy_id, no_exp, pk_num)
    if allergy is None:
        raise VisitDomainError("ALLERGY_NOT_FOUND", "Alergia no encontrada.", 404)

    with transaction.atomic():
        allergy = AllergyRepository.deactivate(allergy, updated_by_id=actor_id)

        audit_hook(
            resource_id=allergy.id_allergy,
            datos_antes={"isActive": True},
            datos_despues={"isActive": False},
            strict=True,
        )

    return AllergyRepository.to_contract(allergy)
