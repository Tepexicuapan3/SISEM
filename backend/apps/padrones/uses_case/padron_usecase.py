"""
Inscripcion y baja en los padrones clinicos (P-04).

Reglas:
- Permisos propios: clinico:padrones:read (consulta) y clinico:padrones:write
  (inscribir / dar de baja).
- El paciente se resuelve con PatientRepository.get_or_create, el mismo
  contrato que usa la historia clinica.
- Centro: el indicado o, si no se indica, el de adscripcion del usuario.
- Una sola inscripcion activa por paciente y padecimiento; la baja es logica,
  por inscripcion, con motivo de catalogo y fecha no futura.
- Los diagnosticos CIE-10 sensibles se redactan segun quien consulta, igual
  que en el resto del expediente.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.authentication.services.permission_dependencies import evaluate_permission_requirement
from apps.catalogos.models import CatCentroAtencion, CatCies, Discapacidades, MotivoBajaPadron
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted
from apps.padrones.models import ChronicEnrollment, DisabilityEnrollment, RegistryStatus
from apps.recepcion.services.errors import VisitDomainError

READ_REQUIREMENT = {"allOf": ["clinico:padrones:read"]}
WRITE_REQUIREMENT = {"allOf": ["clinico:padrones:write"]}
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class RegistryKind:
    key: str
    model: type
    item_field: str  # FK del padecimiento en el modelo
    item_model: type
    item_label: str


KINDS = {
    "cronicos": RegistryKind("cronicos", ChronicEnrollment, "cie", CatCies, "El diagnóstico CIE-10"),
    "discapacidad": RegistryKind(
        "discapacidad", DisabilityEnrollment, "disability", Discapacidades, "La discapacidad",
    ),
}


def _validation_error(field, message):
    return VisitDomainError("VALIDATION_ERROR", "Hay errores en el formulario", 422, details={field: [message]})


def _ensure(requirement, permissions):
    if not evaluate_permission_requirement(requirement, permissions or [])["granted"]:
        raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso para ejecutar esta accion.", 403)


def get_kind(kind):
    spec = KINDS.get(kind)
    if spec is None:
        raise VisitDomainError("REGISTRY_NOT_FOUND", "Padrón no encontrado.", 404)
    return spec


def _user_name(user):
    if user is None:
        return None
    profile = getattr(user, "detalle", None)
    return getattr(profile, "nombre_completo", None) or user.usuario


def _patient_name(patient):
    parts = (patient.first_name, patient.paternal_surname, patient.maternal_surname)
    return " ".join(p.strip() for p in parts if p and p.strip()) or None


def _item_payload(spec, enrollment, permissions, roles):
    item = getattr(enrollment, spec.item_field)
    if spec.key == "cronicos":
        code, description, _, restricted = redact_cie_if_restricted(
            code=item.code, description=item.description, permissions=permissions, roles=roles,
        )
        return {"id": code, "code": code, "description": description, "restricted": restricted}
    return {"id": item.pk, "code": item.code, "description": item.name, "restricted": False}


def to_contract(spec, enrollment, *, permissions, roles):
    return {
        "id": enrollment.id,
        "registry": spec.key,
        "noExp": enrollment.no_exp,
        "pkNum": enrollment.pk_num,
        "patientName": _patient_name(enrollment.patient),
        "item": _item_payload(spec, enrollment, permissions, roles),
        "center": {"id": enrollment.center_id, "name": enrollment.center.name},
        "enrolledOn": enrollment.enrolled_on,
        "enrolledBy": _user_name(enrollment.enrolled_by),
        "notes": enrollment.notes,
        "status": enrollment.status,
        "discharge": None if enrollment.status == RegistryStatus.ACTIVO else {
            "reasonId": enrollment.discharge_reason_id,
            "reason": getattr(enrollment.discharge_reason, "name", None),
            "detail": enrollment.discharge_detail,
            "on": enrollment.discharged_on,
            "by": _user_name(enrollment.discharged_by),
        },
    }


def _base_queryset(spec):
    return spec.model.objects.select_related(
        "patient", "center", spec.item_field, "enrolled_by__detalle",
        "discharge_reason", "discharged_by__detalle",
    )


def list_enrollments(kind, *, permissions, roles=None, no_exp=None, pk_num=None, center_id=None,
                     status=None, page=1, page_size=20):
    _ensure(READ_REQUIREMENT, permissions)
    spec = get_kind(kind)
    qs = _base_queryset(spec)
    if no_exp:
        qs = qs.filter(no_exp=no_exp)
        if pk_num is not None:
            qs = qs.filter(pk_num=pk_num)
    if center_id:
        qs = qs.filter(center_id=center_id)
    if status:
        if status not in RegistryStatus.values:
            raise _validation_error("status", "Debe ser 'activo' o 'baja'.")
        qs = qs.filter(status=status)

    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), MAX_PAGE_SIZE)
    total = qs.count()
    rows = qs.order_by("-enrolled_on", "-id")[(page - 1) * page_size: page * page_size]
    return {
        "items": [to_contract(spec, e, permissions=permissions, roles=roles or []) for e in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": max((total + page_size - 1) // page_size, 1),
    }


def search_options(kind, *, search, permissions, roles=None, limit=20):
    """Opciones para inscribir, con el permiso del padron (no el de consulta
    ni el de admin de catalogos). Los CIE-10 sensibles que el usuario no puede
    ver se omiten: una opcion redactada no sirve para elegir."""
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    term = (search or "").strip()
    if len(term) < 2:
        return {"items": []}
    if spec.key == "cronicos":
        qs = CatCies.objects.filter(is_active=True).filter(
            Q(code__istartswith=term) | Q(description__icontains=term)
        ).order_by("code")
        items = []
        for cie in qs[: limit * 3]:
            _, _, _, restricted = redact_cie_if_restricted(
                code=cie.code, description=cie.description, permissions=permissions, roles=roles or [],
            )
            if not restricted:
                items.append({"id": cie.code, "code": cie.code, "description": cie.description})
            if len(items) >= limit:
                break
        return {"items": items}
    qs = Discapacidades.objects.filter(is_active=True).filter(
        Q(code__istartswith=term) | Q(name__icontains=term)
    ).order_by("code")[:limit]
    return {"items": [{"id": d.pk, "code": d.code, "description": d.name} for d in qs]}


def _assignment_center_id(user):
    try:
        return user.detalle.id_centro_atencion_id
    except Exception:
        return None


def _resolve_center(center_id, actor):
    center_id = center_id or _assignment_center_id(actor)
    if not center_id:
        raise _validation_error("centerId", "Indica el centro: el usuario no tiene centro de adscripción.")
    center = CatCentroAtencion.objects.filter(pk=center_id, is_active=True).first()
    if center is None:
        raise _validation_error("centerId", "El centro no existe o no está activo.")
    return center


def _ensure_not_future(field, value):
    if value > timezone.localdate():
        raise _validation_error(field, "La fecha no puede ser futura.")


def enroll(kind, *, no_exp, pk_num, item_id, center_id=None, enrolled_on=None, notes=None,
           actor, permissions):
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    no_exp = (no_exp or "").strip()
    if not no_exp:
        raise _validation_error("noExp", "El expediente es obligatorio.")
    item = spec.item_model.objects.filter(pk=item_id, is_active=True).first()
    if item is None:
        raise _validation_error("itemId", f"{spec.item_label} no existe o no está activo.")
    center = _resolve_center(center_id, actor)
    enrolled_on = enrolled_on or timezone.localdate()
    _ensure_not_future("enrolledOn", enrolled_on)

    try:
        with transaction.atomic():
            patient, _ = PatientRepository.get_or_create(no_exp, pk_num or 0, created_by_id=actor.pk)
            already = spec.model.objects.filter(
                patient=patient, status=RegistryStatus.ACTIVO, **{spec.item_field: item},
            ).exists()
            if already:
                raise VisitDomainError(
                    "ALREADY_ENROLLED", "El paciente ya está inscrito en el padrón por ese padecimiento.", 409,
                )
            enrollment = spec.model.objects.create(
                no_exp=no_exp, pk_num=pk_num or 0, patient=patient, center=center,
                enrolled_on=enrolled_on, enrolled_by=actor, notes=(notes or "").strip() or None,
                **{spec.item_field: item},
            )
    except IntegrityError as exc:  # carrera contra el unique de inscripcion activa
        raise VisitDomainError(
            "ALREADY_ENROLLED", "El paciente ya está inscrito en el padrón por ese padecimiento.", 409,
        ) from exc
    return _base_queryset(spec).get(pk=enrollment.pk)


def discharge(kind, enrollment_id, *, reason_id, detail=None, discharged_on=None, actor, permissions):
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    reason = MotivoBajaPadron.objects.filter(pk=reason_id, is_active=True).first()
    if reason is None:
        raise _validation_error("reasonId", "El motivo de baja no existe o no está activo.")
    discharged_on = discharged_on or timezone.localdate()
    _ensure_not_future("dischargedOn", discharged_on)

    with transaction.atomic():
        enrollment = spec.model.objects.select_for_update().filter(pk=enrollment_id).first()
        if enrollment is None:
            raise VisitDomainError("ENROLLMENT_NOT_FOUND", "Inscripción no encontrada.", 404)
        if enrollment.status != RegistryStatus.ACTIVO:
            raise VisitDomainError("ENROLLMENT_ALREADY_DISCHARGED", "La inscripción ya está dada de baja.", 409)
        if discharged_on < enrollment.enrolled_on:
            raise _validation_error("dischargedOn", "La baja no puede ser anterior a la inscripción.")
        enrollment.status = RegistryStatus.BAJA
        enrollment.discharge_reason = reason
        enrollment.discharge_detail = (detail or "").strip() or None
        enrollment.discharged_on = discharged_on
        enrollment.discharged_by = actor
        enrollment.save(update_fields=[
            "status", "discharge_reason", "discharge_detail", "discharged_on", "discharged_by", "updated_at",
        ])
    return _base_queryset(spec).get(pk=enrollment.pk)
