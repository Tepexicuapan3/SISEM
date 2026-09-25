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

# `recepcion:incapacidad:read` (change `incapacidad-medica-recepcion-frontend`)
# es de SOLO LECTURA -- solo se acepta como alternativa a
# `clinico:consultas:read` para consultar el historial de incapacidades
# (GET), nunca para crearlas (POST sigue usando ensure_doctor_role/
# DOCTOR_CONSULTATION_PERMISSION_REQUIREMENT exclusivamente).
DOCTOR_OR_INCAPACIDAD_READ_PERMISSION_REQUIREMENT = {
    "anyOf": ["clinico:consultas:read", "recepcion:incapacidad:read"]
}

CIE_SEARCH_MIN_LENGTH = 2

# `SavePrescriptionsSerializer.items` no acota la cantidad de indicaciones
# (ver serializers.py) -- se acota aca solo para el snapshot de auditoria de
# `datos_despues` (A3 fila #15), igual que en PrescriptionRepository para
# `datos_antes`. `itemsCount` siempre refleja el total real, sin truncar.
_AUDIT_PRESCRIPTION_ITEMS_LIMIT = 50


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


def ensure_doctor_or_incapacidad_read_role(roles, permissions=None):
    """
    Guard de SOLO LECTURA para `get_patient_medical_leaves` (GET). Acepta
    rol DOCTOR / `clinico:consultas:read` (igual que ensure_doctor_role) O
    `recepcion:incapacidad:read` -- este ultimo NO debe usarse para ninguna
    accion de escritura (ver create_medical_leave, que sigue llamando
    ensure_doctor_role a secas).
    """
    normalized_roles = {(role or "").strip().upper() for role in roles}
    if ROLE_DOCTOR in normalized_roles:
        return

    permission_state = evaluate_permission_requirement(
        DOCTOR_OR_INCAPACIDAD_READ_PERMISSION_REQUIREMENT,
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


def start_consultation(visit_id, roles, permissions=None, doctor_id=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    visit = _get_visit_or_error(visit_id)

    next_state = transition_visit_state(
        current_state=visit.status,
        target_state="en_consulta",
        actor_role=ROLE_DOCTOR,
    )

    # atomic() agregado por A0.2 (bug de atomicidad preexistente: update_status
    # + log_status_change eran 2 writes sin proteccion) -- se mantiene
    # independientemente de que el hook, tras A7, sea strict=False.
    with transaction.atomic():
        # Gotcha A4.4: VisitRepository.update_status muta la instancia en
        # memoria y devuelve el MISMO objeto -- previous_status se captura
        # ANTES de llamarlo.
        previous_status = visit.status
        visit = VisitRepository.update_status(visit, next_state)
        VisitRepository.log_status_change(
            visit=visit,
            from_status=previous_status,
            to_status=next_state,
            changed_by_id=doctor_id,
        )
        audit_hook(
            resource_id=visit.id_visit,
            datos_antes={"status": previous_status},
            datos_despues={"status": next_state, "doctorId": doctor_id},
            strict=False,
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
    *,
    audit_hook,
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
        consultation, _, previous_snapshot = ConsultationRepository.upsert_for_visit(
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
        audit_hook(
            resource_id=consultation.id_consultation,
            datos_antes=previous_snapshot,
            datos_despues={
                "visitId": visit.id_visit,
                "primaryDiagnosis": consultation.primary_diagnosis,
                "cieCode": consultation.cie_id,
                "finalNoteLen": len(consultation.final_note) if consultation.final_note else None,
                "hasSubjective": bool(consultation.subjective),
                "hasObjective": bool(consultation.objective),
                "hasAssessment": bool(consultation.assessment),
                "hasPlan": bool(consultation.plan),
            },
            strict=False,
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
    *,
    audit_hook,
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
        prescription, _, previous_snapshot = PrescriptionRepository.upsert_for_visit(
            visit,
            items=normalized_items,
            created_by_id=doctor_id,
            updated_by_id=doctor_id,
        )
        audit_hook(
            resource_id=prescription.id_prescription,
            datos_antes=previous_snapshot,
            datos_despues={
                "visitId": visit.id_visit,
                "itemsCount": len(prescription.items or []),
                "items": list(prescription.items or [])[:_AUDIT_PRESCRIPTION_ITEMS_LIMIT],
            },
            strict=True,
        )

    return {
        "visitId": visit.id_visit,
        "status": visit.status,
        "items": list(prescription.items or []),
    }


def _close_consultation_datos_antes(previous_visit_status, previous_snapshot):
    return {
        "visitStatus": previous_visit_status,
        "primaryDiagnosis": previous_snapshot["primaryDiagnosis"] if previous_snapshot else None,
        "cieCode": previous_snapshot["cieCode"] if previous_snapshot else None,
        "finalNoteLen": previous_snapshot["finalNoteLen"] if previous_snapshot else None,
    }


def _close_consultation_datos_despues(visit, consultation, *, is_replay):
    return {
        "visitId": visit.id_visit,
        "visitStatus": "cerrada",
        "primaryDiagnosis": consultation.primary_diagnosis,
        "cieCode": consultation.cie_id,
        "finalNoteLen": len(consultation.final_note) if consultation.final_note else None,
        "isReplay": is_replay,
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
    *,
    audit_hook,
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
            # Path idempotente: no hay mutacion de dominio, no hace falta
            # atomic(). Invariante del spec: datos_antes == datos_despues,
            # isReplay=True, strict=False (A7) -- un fallo del hook nunca
            # convierte este 200 en 500.
            replay_snapshot = _close_consultation_datos_despues(
                visit, existing_consultation, is_replay=True,
            )
            audit_hook(
                resource_id=existing_consultation.id_consultation,
                datos_antes=replay_snapshot,
                datos_despues=replay_snapshot,
                strict=False,
            )
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
            consultation, _, previous_snapshot = ConsultationRepository.upsert_for_visit(
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
            # La visita ya estaba "cerrada" (guarda del if externo) -- este
            # path solo crea la fila de consulta que faltaba, no transiciona
            # estado. strict=False (A7): un fallo del hook no revierte esto.
            audit_hook(
                resource_id=consultation.id_consultation,
                datos_antes=_close_consultation_datos_antes(visit.status, previous_snapshot),
                datos_despues=_close_consultation_datos_despues(visit, consultation, is_replay=False),
                strict=False,
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
        consultation, _, previous_snapshot = ConsultationRepository.upsert_for_visit(
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
        # Gotcha A4.4: VisitRepository.update_status muta la instancia en
        # memoria -- previous_status ya se capturo ANTES del atomic, mientras
        # visit.status todavia era el valor previo.
        visit = VisitRepository.update_status(visit, next_state)
        VisitRepository.log_status_change(
            visit=visit,
            from_status=previous_status,
            to_status=next_state,
            changed_by_id=doctor_id,
        )
        # Invariante A4.3: exactamente 1 evento ConsultationClosed por
        # request aunque haya 3 escrituras de dominio en este path.
        # strict=False (A7): un fallo del hook no revierte el cierre.
        audit_hook(
            resource_id=consultation.id_consultation,
            datos_antes=_close_consultation_datos_antes(previous_status, previous_snapshot),
            datos_despues=_close_consultation_datos_despues(visit, consultation, is_replay=False),
            strict=False,
        )

    return {
        "visit": VisitRepository.to_contract(visit),
        "consultation": ConsultationRepository.to_contract(consultation),
    }


def add_consultation_addendum(
    visit_id,
    roles,
    *,
    text,
    doctor_id,
    permissions=None,
):
    """
    Nota de aclaracion sobre una consulta YA CERRADA (ver docstring de
    ConsultationAddendum). Si la visita sigue "en_consulta", el medico debe
    corregir directo con save_diagnosis -- una adenda es para cuando ya no
    se puede sobreescribir el registro original.
    """
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    if visit.status != "cerrada":
        raise VisitDomainError(
            "VISIT_STATE_INVALID",
            "Solo se puede agregar una nota de aclaracion a una consulta ya cerrada. "
            "Si la consulta sigue en curso, corregi el diagnostico directamente.",
            409,
        )

    consultation = _get_consultation_or_error(visit)

    normalized_text = (text or "").strip()
    if not normalized_text:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"text": ["El texto de la aclaracion es obligatorio."]},
        )

    addendum = ConsultationRepository.add_addendum(
        consultation, text=normalized_text, created_by_id=doctor_id,
    )
    return ConsultationRepository.addendum_to_contract(addendum)


def get_consultation_addenda(visit_id, roles, permissions=None):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    consultation = _get_consultation_or_error(visit)

    addenda = ConsultationRepository.list_addenda(consultation)
    items = [ConsultationRepository.addendum_to_contract(a) for a in addenda]
    return {"items": items, "total": len(items)}


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
    audit_hook,
):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    consultation = _get_consultation_or_error(visit)

    diagnosis = VisitDiagnosisRepository.get_by_id(diagnosis_id)
    if diagnosis is None or diagnosis.consultation_id != consultation.id_consultation:
        raise VisitDomainError(
            "DIAGNOSIS_NOT_FOUND", "Diagnostico secundario no encontrado.", 404,
        )

    with transaction.atomic():
        # Gotcha A4.4: VisitDiagnosisRepository.cancel muta la instancia en
        # memoria y devuelve el MISMO objeto -- datos_antes se captura ANTES.
        datos_antes = {"status": diagnosis.status, "cieCode": diagnosis.cie_id}
        diagnosis = VisitDiagnosisRepository.cancel(diagnosis, updated_by_id=doctor_id)
        audit_hook(
            resource_id=diagnosis.id_visit_diagnosis,
            datos_antes=datos_antes,
            datos_despues={"status": diagnosis.status, "cieCode": diagnosis.cie_id},
            strict=True,
        )
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
