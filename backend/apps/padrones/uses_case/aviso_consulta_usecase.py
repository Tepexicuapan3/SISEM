"""
Cronicos, entrega 1 (docs/plans/cronicos-aviso-consulta.md): aviso del padron
dentro de la consulta y sugerencia de inscripcion.

Reglas:
- El aviso lo ve el medico que atiende (clinico:consultas:read) o quien
  consulta el padron (clinico:padrones:read). Solo inscripciones activas.
- La visita se lee por el contrato de recepcion (get_visit_by_id), nunca por
  su modelo; de ella salen el paciente y el centro.
- Se sugiere inscribir cuando el CIE esta activo, pertenece a un programa
  activo, el usuario puede verlo (un CIE sensible redactado no se sugiere) y
  el paciente no esta ya inscrito en ese programa.
- Inscribir sigue pidiendo clinico:padrones:write y las mismas reglas del
  alta del padron (una inscripcion activa por paciente y CIE).
"""

from django.utils import timezone

from apps.authentication.services.permission_dependencies import evaluate_permission_requirement
from apps.catalogos.models import CatCies
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted
from apps.padrones.models import ChronicEnrollment, ChronicProgramCie, EnrollmentSource, RegistryStatus
from apps.recepcion.contracts.visit_flow_contract import get_visit_by_id
from apps.recepcion.services.errors import VisitDomainError

from . import padron_usecase as padron

NOTICE_REQUIREMENT = {"anyOf": ["clinico:consultas:read", "clinico:padrones:read"]}
CHRONIC = padron.KINDS["cronicos"]


def _normalize_cie(code):
    return (code or "").replace(".", "").strip().upper()


def program_for_cie(code):
    """Programa activo del CIE por el prefijo mas largo, o None."""
    normalized = _normalize_cie(code)
    if not normalized:
        return None
    prefixes = [normalized[:size] for size in range(len(normalized), 0, -1)]
    match = (
        ChronicProgramCie.objects.select_related("program")
        .filter(cie_prefix__in=prefixes, program__is_active=True)
        # Todos son prefijos del mismo codigo: el mas largo es el mayor.
        .order_by("-cie_prefix")
        .first()
    )
    return match.program if match else None


def _program_payload(program):
    return {"code": program.code, "name": program.name} if program else None


def _visit_or_404(visit_id):
    visit = get_visit_by_id(visit_id)
    if visit is None:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    return visit


def _suggestion(cie, active, *, permissions, roles):
    normalized = _normalize_cie(cie)
    if not normalized:
        return None
    item = CatCies.objects.filter(is_active=True).filter(code__in={normalized, (cie or "").strip().upper()}).first()
    if item is None:
        return None
    _, _, _, restricted = redact_cie_if_restricted(
        code=item.code, description=item.description, permissions=permissions, roles=roles,
    )
    program = program_for_cie(item.code)
    if restricted or program is None:
        return None
    if any(program_for_cie(enrollment.cie_id) == program for enrollment in active):
        return None
    return {"cie": {"code": item.code, "description": item.description}, "program": _program_payload(program)}


def get_notice(visit_id, *, cie=None, permissions, roles=None):
    padron._ensure(NOTICE_REQUIREMENT, permissions)
    roles = roles or []
    visit = _visit_or_404(visit_id)
    active = list(
        ChronicEnrollment.objects.select_related("cie")
        .filter(patient_id=visit.patient_id, status=RegistryStatus.ACTIVO)
        .order_by("enrolled_on", "id")
    )
    enrollments = []
    for enrollment in active:
        item = padron._item_payload(CHRONIC, enrollment, permissions, roles)
        enrollments.append({
            "id": enrollment.id,
            "item": item,
            # El nombre del programa delataria un diagnostico redactado.
            "program": None if item["restricted"] else _program_payload(program_for_cie(enrollment.cie_id)),
            "enrolledOn": enrollment.enrolled_on,
        })
    return {
        "enrollments": enrollments,
        "suggestion": _suggestion(cie, active, permissions=permissions, roles=roles),
        "canEnroll": evaluate_permission_requirement(padron.WRITE_REQUIREMENT, permissions or [])["granted"],
    }


def enroll_from_visit(visit_id, *, item_id, notes=None, actor, permissions):
    padron._ensure(padron.WRITE_REQUIREMENT, permissions)
    visit = _visit_or_404(visit_id)
    item = CatCies.objects.filter(pk=(item_id or "").strip(), is_active=True).first()
    if item is None:
        raise padron._validation_error("itemId", f"{CHRONIC.item_label} no existe o no está activo.")
    center = padron._resolve_center(visit.centro_id, actor)
    return padron.create_enrollment(
        CHRONIC, get_patient=lambda: visit.patient, item=item, center=center,
        enrolled_on=timezone.localdate(), notes=notes, actor=actor,
        extra={"source": EnrollmentSource.CONSULTA, "visit": visit},
    )
