from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.authentication.services.authorization_service import has_capability
from apps.somatometria.services.bmi_service import calculate_bmi
from apps.somatometria.services.visit_flow_service import (
    VisitFlowError,
    get_visit_flow_service,
)
from apps.somatometria.repositories.vitals_repository import VitalsRepository

SOMATOMETRIA_CAPTURE_CAPABILITY = "flow.somatometria.capture"
SOMATOMETRIA_EDIT_CAPABILITY = "flow.somatometria.edit"


def ensure_somatometria_capability(permissions, capability):
    """
    D7 (change `somatometria-modulo-integral`): version parametrizada --
    `capture_vitals` (POST) sigue exigiendo `SOMATOMETRIA_CAPTURE_CAPABILITY`
    y la edicion auditada (PATCH) exige `SOMATOMETRIA_EDIT_CAPABILITY`, sin
    duplicar la logica de chequeo entre ambas.
    """
    if has_capability(permissions or [], capability):
        return

    raise VisitFlowError(
        "ROLE_NOT_ALLOWED",
        "No tenes permiso para ejecutar esta accion.",
        403,
    )


def ensure_somatometria_role(roles, permissions=None):
    """
    Alias retrocompatible: `views.py` y los tests existentes importan este
    nombre para el chequeo de captura (POST). Delega en
    `ensure_somatometria_capability` con la capability de captura.
    """
    del roles
    ensure_somatometria_capability(permissions, SOMATOMETRIA_CAPTURE_CAPABILITY)


def capture_vitals(visit_id, vitals_payload, *, actor=None, visit_flow_service=None):
    visit_flow = visit_flow_service or get_visit_flow_service()

    visit = visit_flow.get_by_id(visit_id)
    if not visit:
        raise VisitFlowError(
            "VISIT_NOT_FOUND",
            "Visita no encontrada.",
            404,
        )

    # Precondicion normal (D2): una visita solo se captura UNA vez. El
    # `IntegrityError` de mas abajo es la red de seguridad para la carrera
    # entre dos POST concurrentes, no el camino esperado.
    if VitalsRepository.get_vitals_by_visit_id(visit_id) is not None:
        raise VisitFlowError(
            "VITALS_ALREADY_CAPTURED",
            "Esta visita ya tiene signos vitales capturados. Usa la edicion para corregirlos.",
            409,
        )

    payload = dict(vitals_payload)
    reused_from_visit_id = payload.pop("reusedFromVisitId", None)
    reused_from = _resolve_reused_source(visit, reused_from_visit_id)

    next_state = visit_flow.resolve_next_state(
        visit.status,
        vitals_complete=_has_minimum_vitals(payload),
    )

    payload["bmi"] = _calculate_bmi(payload["weightKg"], payload["heightCm"])

    try:
        with transaction.atomic():
            vital_signs = VitalsRepository.create_for_visit(
                visit,
                payload,
                reused_from=reused_from,
                captured_by=actor,
            )
            visit_flow.update_status(visit, next_state)
    except IntegrityError as exc:
        raise VisitFlowError(
            "VITALS_ALREADY_CAPTURED",
            "Esta visita ya tiene signos vitales capturados. Usa la edicion para corregirlos.",
            409,
        ) from exc

    return {
        "visitId": visit.id_visit,
        "status": next_state,
        "vitals": VitalsRepository.to_contract(vital_signs),
    }


def get_latest_vitals_for_visit(visit_id, *, visit_flow_service=None):
    visit_flow = visit_flow_service or get_visit_flow_service()

    visit = visit_flow.get_by_id(visit_id)
    if not visit:
        raise VisitFlowError(
            "VISIT_NOT_FOUND",
            "Visita no encontrada.",
            404,
        )

    latest = VitalsRepository.get_latest_for_patient(visit.patient_id)
    today_capture = VitalsRepository.get_latest_today_for_patient(
        visit.patient_id,
        exclude_visit_id=visit.id_visit,
    )

    return {
        "vitals": VitalsRepository.latest_to_contract(latest) if latest else None,
        "todayCapture": (
            VitalsRepository.today_to_contract(today_capture)
            if today_capture
            else None
        ),
    }


def _resolve_reused_source(visit, reused_visit_id):
    """
    Valida el reuso de una captura de signos vitales del mismo dia. Las 4
    reglas (mismo orden que los codigos 422 esperados por el spec):
    no reusar la propia visita, el origen debe existir, debe ser la misma
    persona (mismo id_paciente) y debe haber sido capturado HOY (dia calendario
    local). Devuelve la `Visit` origen (o None si no hay reuso).
    """
    if reused_visit_id is None:
        return None

    if reused_visit_id == visit.id_visit:
        raise VisitFlowError(
            "REUSE_SAME_VISIT",
            "No se puede reusar la captura de esta misma visita.",
            422,
        )

    source = VitalsRepository.get_vitals_by_visit_id(reused_visit_id)
    if source is None:
        raise VisitFlowError(
            "REUSE_SOURCE_NOT_FOUND",
            "La captura de origen no existe.",
            422,
        )

    if source.id_visit.patient_id != visit.patient_id:
        raise VisitFlowError(
            "REUSE_PATIENT_MISMATCH",
            "La captura de origen pertenece a otra persona.",
            422,
        )

    if timezone.localtime(source.fch_alta).date() != timezone.localdate():
        raise VisitFlowError(
            "REUSE_NOT_TODAY",
            "Solo se pueden reusar signos vitales tomados hoy.",
            422,
        )

    return source.id_visit


def _has_minimum_vitals(payload):
    return (
        payload.get("temperatureC") is not None
        and payload.get("oxygenSaturationPct") is not None
    )


# Re-exportado para no romper a quien ya importaba `_calculate_bmi` desde
# este modulo (D9): el calculo real vive en `bmi_service.calculate_bmi`,
# compartido con la edicion auditada (Fase 3) para que POST y PATCH nunca
# diverjan de formula/redondeo.
_calculate_bmi = calculate_bmi
