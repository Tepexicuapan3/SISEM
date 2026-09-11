from django.db import transaction

from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.consulta_medica.repositories.cies_repository import CiesRepository
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
from apps.consulta_medica.repositories.visit_diagnosis_repository import VisitDiagnosisRepository
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_state_machine_usecase import (
    ROLE_DOCTOR,
    transition_visit_state,
)

DOCTOR_CONSULTATION_PERMISSION_REQUIREMENT = {
    "allOf": ["clinico:consultas:read"]
}

CIE_SEARCH_MIN_LENGTH = 2


def ensure_doctor_role(roles, permissions=None):
    normalized_roles = {(role or "").strip().upper() for role in roles}
    if ROLE_DOCTOR in normalized_roles:
        return

    permission_state = evaluate_permission_requirement(
        DOCTOR_CONSULTATION_PERMISSION_REQUIREMENT,
        permissions or [],
    )
    if permission_state["granted"]:
        return

    raise VisitDomainError(
        "ROLE_NOT_ALLOWED",
        "No tenes permiso para ejecutar esta accion.",
        403,
    )


def _get_visit_or_error(visit_id):
    visit = VisitRepository.get_by_id(visit_id)
    if not visit:
        raise VisitDomainError(
            "VISIT_NOT_FOUND",
            "Visita no encontrada.",
            404,
        )
    return visit


def _ensure_visit_in_consultation(visit):
    if visit.status != "en_consulta":
        raise VisitDomainError(
            "VISIT_STATE_INVALID",
            "La visita debe estar en consulta para ejecutar esta accion.",
            409,
        )


def _normalize_prescription_items(items):
    normalized_items = []
    for item in items or []:
        normalized_item = (item or "").strip()
        if normalized_item:
            normalized_items.append(normalized_item)
    return normalized_items


def _normalize_cie_code(cie_code):
    normalized = (cie_code or "").strip().upper()
    return normalized or None


def _resolve_cie_code_or_error(cie_code):
    normalized_code = _normalize_cie_code(cie_code)
    if not normalized_code:
        return None

    cie_match = CiesRepository.get_active_by_code(normalized_code)
    if cie_match is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"cieCode": ["La clave CIE no existe o no esta activa."]},
        )

    return normalized_code


def start_consultation(visit_id, roles, permissions=None, doctor_id=None):
    ensure_doctor_role(roles, permissions)
    visit = _get_visit_or_error(visit_id)

    previous_status = visit.status
    next_state = transition_visit_state(
        current_state=visit.status,
        target_state="en_consulta",
        actor_role=ROLE_DOCTOR,
    )
    visit = VisitRepository.update_status(visit, next_state)
    VisitRepository.log_status_change(
        visit=visit,
        from_status=previous_status,
        to_status=next_state,
        changed_by_id=doctor_id,
    )
    return VisitRepository.to_contract(visit)


def _normalize_soap_field(value):
    normalized = (value or "").strip()
    return normalized or None


def save_diagnosis(
    visit_id,
    roles,
    primary_diagnosis,
    final_note,
    doctor_id,
    permissions=None,
    cie_code=None,
    subjective=None,
    objective=None,
    assessment=None,
    plan=None,
):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    _ensure_visit_in_consultation(visit)

    normalized_primary_diagnosis = (primary_diagnosis or "").strip()
    normalized_final_note = (final_note or "").strip()
    normalized_cie_code = _resolve_cie_code_or_error(cie_code)
    normalized_subjective = _normalize_soap_field(subjective)
    normalized_objective = _normalize_soap_field(objective)
    normalized_assessment = _normalize_soap_field(assessment)
    normalized_plan = _normalize_soap_field(plan)
    if not normalized_primary_diagnosis or not normalized_final_note:
        raise VisitDomainError(
            "VISIT_STATE_INVALID",
            "No se puede guardar diagnostico: falta diagnostico o nota final.",
            409,
        )

    with transaction.atomic():
        consultation, _ = ConsultationRepository.upsert_for_visit(
            visit,
            doctor_id=doctor_id,
            primary_diagnosis=normalized_primary_diagnosis,
            cie_code=normalized_cie_code,
            final_note=normalized_final_note,
            subjective=normalized_subjective,
            objective=normalized_objective,
            assessment=normalized_assessment,
            plan=normalized_plan,
            created_by_id=doctor_id,
            updated_by_id=doctor_id,
        )

    return {
        "visitId": visit.id_visit,
        "status": visit.status,
        "primaryDiagnosis": consultation.primary_diagnosis,
        "cieCode": consultation.cie_id,
        "finalNote": consultation.final_note,
        "subjective": consultation.subjective,
        "objective": consultation.objective,
        "assessment": consultation.assessment,
        "plan": consultation.plan,
    }


def save_prescriptions(
    visit_id,
    roles,
    items,
    doctor_id,
    permissions=None,
):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    _ensure_visit_in_consultation(visit)

    normalized_items = _normalize_prescription_items(items)
    if not normalized_items:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"items": ["Debes indicar al menos una receta."]},
        )

    with transaction.atomic():
        prescription, _ = PrescriptionRepository.upsert_for_visit(
            visit,
            items=normalized_items,
            created_by_id=doctor_id,
            updated_by_id=doctor_id,
        )

    return {
        "visitId": visit.id_visit,
        "status": visit.status,
        "items": list(prescription.items or []),
    }


def close_consultation(
    visit_id,
    roles,
    primary_diagnosis,
    final_note,
    doctor_id,
    permissions=None,
    cie_code=None,
    subjective=None,
    objective=None,
    assessment=None,
    plan=None,
):
    ensure_doctor_role(roles, permissions)
    normalized_primary_diagnosis = (primary_diagnosis or "").strip()
    normalized_final_note = (final_note or "").strip()
    normalized_cie_code = _resolve_cie_code_or_error(cie_code)
    normalized_subjective = _normalize_soap_field(subjective)
    normalized_objective = _normalize_soap_field(objective)
    normalized_assessment = _normalize_soap_field(assessment)
    normalized_plan = _normalize_soap_field(plan)
    if not normalized_cie_code:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"cieCode": ["El código CIE-10 es obligatorio para cerrar la consulta."]},
        )

    visit = _get_visit_or_error(visit_id)

    if visit.status == "cerrada":
        existing_consultation = ConsultationRepository.get_by_visit(visit)
        if (
            existing_consultation is not None
            and existing_consultation.primary_diagnosis == normalized_primary_diagnosis
            and existing_consultation.cie_id == normalized_cie_code
            and existing_consultation.final_note == normalized_final_note
            and existing_consultation.subjective == normalized_subjective
            and existing_consultation.objective == normalized_objective
            and existing_consultation.assessment == normalized_assessment
            and existing_consultation.plan == normalized_plan
        ):
            return {
                "visit": VisitRepository.to_contract(visit),
                "consultation": ConsultationRepository.to_contract(existing_consultation),
            }

        if existing_consultation is not None:
            raise VisitDomainError(
                "CONFLICT_DUPLICATE_ACTION",
                "La consulta ya fue cerrada con datos diferentes.",
                409,
            )

        with transaction.atomic():
            consultation, _ = ConsultationRepository.upsert_for_visit(
                visit,
                doctor_id=doctor_id,
                primary_diagnosis=normalized_primary_diagnosis,
                cie_code=normalized_cie_code,
                final_note=normalized_final_note,
                subjective=normalized_subjective,
                objective=normalized_objective,
                assessment=normalized_assessment,
                plan=normalized_plan,
                created_by_id=doctor_id,
                updated_by_id=doctor_id,
            )

        return {
            "visit": VisitRepository.to_contract(visit),
            "consultation": ConsultationRepository.to_contract(consultation),
        }

    next_state = transition_visit_state(
        current_state=visit.status,
        target_state="cerrada",
        actor_role=ROLE_DOCTOR,
        primary_diagnosis=normalized_primary_diagnosis,
        final_note=normalized_final_note,
    )

    previous_status = visit.status
    with transaction.atomic():
        consultation, _ = ConsultationRepository.upsert_for_visit(
            visit,
            doctor_id=doctor_id,
            primary_diagnosis=normalized_primary_diagnosis,
            cie_code=normalized_cie_code,
            final_note=normalized_final_note,
            subjective=normalized_subjective,
            objective=normalized_objective,
            assessment=normalized_assessment,
            plan=normalized_plan,
            created_by_id=doctor_id,
            updated_by_id=doctor_id,
        )
        visit = VisitRepository.update_status(visit, next_state)
        VisitRepository.log_status_change(
            visit=visit,
            from_status=previous_status,
            to_status=next_state,
            changed_by_id=doctor_id,
        )

    return {
        "visit": VisitRepository.to_contract(visit),
        "consultation": ConsultationRepository.to_contract(consultation),
    }


def _get_consultation_or_error(visit):
    consultation = ConsultationRepository.get_by_visit(visit)
    if consultation is None:
        raise VisitDomainError(
            "CONSULTATION_NOT_FOUND",
            "Primero debes guardar el diagnostico de esta consulta.",
            409,
        )
    return consultation


def add_secondary_diagnosis(
    visit_id,
    roles,
    *,
    cie_code,
    notes=None,
    doctor_id,
    permissions=None,
):
    """
    Agrega un diagnostico secundario/comorbilidad a la consulta -- el
    diagnostico PRINCIPAL sigue siendo VisitConsultation.primary_diagnosis/
    cie (save_diagnosis/close_consultation). Equivalente moderno de
    det_hisnotcie del legado (N codigos CIE-10 por nota, en tabla detalle).
    """
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    consultation = _get_consultation_or_error(visit)

    normalized_cie_code = _normalize_cie_code(cie_code)
    if not normalized_cie_code:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"cieCode": ["cieCode es obligatorio."]},
        )

    cie = CiesRepository.get_active_by_code(normalized_cie_code)
    if cie is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"cieCode": ["La clave CIE no existe o no esta activa."]},
        )

    if VisitDiagnosisRepository.get_active_by_consultation_and_cie(consultation, cie):
        raise VisitDomainError(
            "DIAGNOSIS_ALREADY_EXISTS",
            "Ese codigo CIE-10 ya esta agregado como diagnostico de esta consulta.",
            409,
        )

    normalized_notes = (notes or "").strip() or None

    diagnosis = VisitDiagnosisRepository.create(
        consultation=consultation,
        cie=cie,
        notes=normalized_notes,
        created_by_id=doctor_id,
        updated_by_id=doctor_id,
    )
    return VisitDiagnosisRepository.to_contract(diagnosis)


def cancel_secondary_diagnosis(
    visit_id,
    diagnosis_id,
    roles,
    *,
    doctor_id,
    permissions=None,
):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    consultation = _get_consultation_or_error(visit)

    diagnosis = VisitDiagnosisRepository.get_by_id(diagnosis_id)
    if diagnosis is None or diagnosis.consultation_id != consultation.id_consultation:
        raise VisitDomainError(
            "DIAGNOSIS_NOT_FOUND", "Diagnostico secundario no encontrado.", 404,
        )

    diagnosis = VisitDiagnosisRepository.cancel(diagnosis, updated_by_id=doctor_id)
    return VisitDiagnosisRepository.to_contract(diagnosis)


def get_secondary_diagnoses(visit_id, roles, permissions=None):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    consultation = _get_consultation_or_error(visit)

    diagnoses = VisitDiagnosisRepository.list_for_consultation(consultation)
    items = [VisitDiagnosisRepository.to_contract(d) for d in diagnoses]
    return {"items": items, "total": len(items)}


def search_cies(search, roles, permissions=None, *, limit=10):
    ensure_doctor_role(roles, permissions)

    normalized_search = (search or "").strip()
    if len(normalized_search) < CIE_SEARCH_MIN_LENGTH:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={
                "search": [
                    "Debes ingresar al menos 2 caracteres para buscar CIE.",
                ]
            },
        )

    results = CiesRepository.search_active(normalized_search, limit=limit)
    return {
        "items": [
            {
                "code": item.code,
                "description": item.description,
                "version": item.version,
            }
            for item in results
        ],
        "total": len(results),
    }
