from django.db import transaction
from django.utils import timezone

from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.catalogos.models import (
    CatCies,
    CatClasificacionCirugia,
    CatMotivoCancelacionCirugia,
    CatTipoCirugia,
)
from apps.administracion.models import CatClinica
from apps.cirugias.models import SurgerySchedule
from apps.cirugias.repositories.surgery_repository import SurgeryRepository
from apps.medicos.models import CatMedico
from apps.recepcion.services.errors import VisitDomainError

SURGERY_READ_REQUIREMENT = {"allOf": ["clinico:cirugias:read"]}
SURGERY_WRITE_REQUIREMENT = {"allOf": ["clinico:cirugias:write"]}


def _ensure_permission(permissions, requirement):
    state = evaluate_permission_requirement(requirement, permissions or [])
    if state["granted"]:
        return
    raise VisitDomainError(
        "ROLE_NOT_ALLOWED", "No tienes permiso para ejecutar esta accion.", 403,
    )


def ensure_surgery_read(permissions=None):
    _ensure_permission(permissions, SURGERY_READ_REQUIREMENT)


def ensure_surgery_write(permissions=None):
    _ensure_permission(permissions, SURGERY_WRITE_REQUIREMENT)


def _resolve_fk_or_error(model, value_id, field_name, label):
    """Resuelve un catalogo `CatalogBase` (con `is_active`) o lanza error."""
    if value_id is None:
        return None
    instance = model.objects.filter(pk=value_id, is_active=True).first()
    if instance is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={field_name: [f"{label} no existe o no esta activo."]},
        )
    return instance


def _resolve_surgeon_or_error(surgeon_id):
    # CatMedico no tiene `is_active` (usa `estatus_medico`); un medico de
    # baja aun puede tener cirugias historicas ligadas, por eso solo se
    # valida existencia -- no se bloquea por estatus en el MVP.
    surgeon = CatMedico.objects.filter(pk=surgeon_id).first()
    if surgeon is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"surgeonId": ["El medico no existe."]},
        )
    return surgeon


def schedule_surgery(
    *,
    no_exp,
    pk_num,
    surgeon_id,
    surgery_type_id,
    classification_id,
    origin_clinic_id=None,
    scheduled_date,
    scheduled_time,
    duration_minutes=None,
    contact_phone=None,
    description=None,
    diagnosis_text=None,
    requirements=None,
    cie_codes=None,
    actor_id,
    permissions=None,
):
    ensure_surgery_write(permissions)

    surgeon = _resolve_surgeon_or_error(surgeon_id)
    surgery_type = _resolve_fk_or_error(CatTipoCirugia, surgery_type_id, "surgeryTypeId", "El tipo de cirugia")
    classification = _resolve_fk_or_error(
        CatClasificacionCirugia, classification_id, "classificationId", "La clasificacion",
    )
    if origin_clinic_id and not CatClinica.objects.filter(pk=origin_clinic_id).exists():
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"originClinicId": ["La clinica de origen no existe."]},
        )

    if SurgeryRepository.has_conflict(
        surgeon, scheduled_date, scheduled_time, duration_minutes,
    ):
        raise VisitDomainError(
            "SURGERY_TIME_CONFLICT",
            "El medico ya tiene una cirugia agendada que se traslapa con ese horario.",
            409,
        )

    folio = f"CIR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{no_exp}"

    with transaction.atomic():
        surgery = SurgeryRepository.create(
            folio=folio,
            no_exp=no_exp,
            pk_num=pk_num or 0,
            surgeon=surgeon,
            surgery_type=surgery_type,
            classification=classification,
            origin_clinic_id=origin_clinic_id or None,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            contact_phone=contact_phone,
            description=description,
            diagnosis_text=diagnosis_text,
            requirements=requirements,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )

        for code in cie_codes or []:
            cie = CatCies.objects.filter(pk=code, is_active=True).first()
            if cie is None:
                raise VisitDomainError(
                    "VALIDATION_ERROR",
                    "Hay errores en el formulario",
                    422,
                    details={"cieCodes": [f"El codigo CIE-10 '{code}' no existe o no esta activo."]},
                )
            SurgeryRepository.add_diagnosis(surgery=surgery, cie=cie, created_by_id=actor_id)

    surgery.refresh_from_db()
    return SurgeryRepository.to_contract(surgery)


def cancel_surgery(surgery_id, *, reason_id, notes=None, actor_id, permissions=None, audit_hook):
    ensure_surgery_write(permissions)

    surgery = SurgeryRepository.get_by_id(surgery_id)
    if surgery is None:
        raise VisitDomainError("SURGERY_NOT_FOUND", "Cirugia no encontrada.", 404)

    if surgery.status == SurgerySchedule.Status.CANCELADA:
        raise VisitDomainError("SURGERY_ALREADY_CANCELLED", "La cirugia ya esta cancelada.", 409)

    reason = CatMotivoCancelacionCirugia.objects.filter(pk=reason_id, is_active=True).first()
    if reason is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"reasonId": ["El motivo de cancelacion no existe o no esta activo."]},
        )

    with transaction.atomic():
        # `SurgeryRepository.cancel` muta `surgery` en memoria y devuelve el
        # MISMO objeto (gotcha B2/A4.4) -- `datos_antes` se captura ANTES.
        datos_antes = {"status": surgery.status}
        surgery = SurgeryRepository.cancel(
            surgery, reason=reason, notes=notes, updated_by_id=actor_id,
        )
        audit_hook(
            resource_id=surgery.id,
            folio=surgery.folio,
            datos_antes=datos_antes,
            datos_despues={
                "status": surgery.status,
                "reasonId": reason.id,
                "reasonName": reason.name,
                "notes": notes,
            },
        )

    return SurgeryRepository.to_contract(surgery)


def list_surgeries(*, permissions=None, **filters):
    ensure_surgery_read(permissions)
    surgeries = SurgeryRepository.list_queryset(**filters)
    items = [SurgeryRepository.to_contract(s) for s in surgeries]
    return {"items": items, "total": len(items)}


def get_surgery_report(fecha_inicio, fecha_fin, *, permissions=None, **filters):
    ensure_surgery_read(permissions)

    if fecha_inicio > fecha_fin:
        raise VisitDomainError(
            "VALIDATION_ERROR", "fechaInicio no puede ser posterior a fechaFin.", 422,
        )

    surgeries = SurgeryRepository.list_queryset(
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, **filters,
    )
    items = [SurgeryRepository.to_report_row(s) for s in surgeries]
    return {
        "items": items,
        "total": len(items),
        "fechaInicio": fecha_inicio,
        "fechaFin": fecha_fin,
    }
