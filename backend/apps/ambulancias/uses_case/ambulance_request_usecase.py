from django.db import transaction
from django.utils import timezone

from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.administracion.models import CatClinica
from apps.ambulancias.models import AmbulanceRequest
from apps.ambulancias.repositories.ambulance_request_repository import AmbulanceRequestRepository
from apps.catalogos.models import (
    CatDestinoAmbulancia,
    CatMotivoTraslado,
    CatTipoServicioAmbulancia,
    CatTipoTraslado,
    Parentesco,
)
from apps.recepcion.services.errors import VisitDomainError

AMBULANCE_READ_REQUIREMENT = {"allOf": ["clinico:ambulancias:read"]}
AMBULANCE_WRITE_REQUIREMENT = {"allOf": ["clinico:ambulancias:write"]}
AMBULANCE_AUTHORIZE_REQUIREMENT = {"allOf": ["clinico:ambulancias:authorize"]}


def _ensure_permission(permissions, requirement):
    state = evaluate_permission_requirement(requirement, permissions or [])
    if state["granted"]:
        return
    raise VisitDomainError(
        "ROLE_NOT_ALLOWED", "No tienes permiso para ejecutar esta accion.", 403,
    )


def ensure_ambulance_read(permissions=None):
    _ensure_permission(permissions, AMBULANCE_READ_REQUIREMENT)


def ensure_ambulance_write(permissions=None):
    _ensure_permission(permissions, AMBULANCE_WRITE_REQUIREMENT)


def ensure_ambulance_authorize(permissions=None):
    _ensure_permission(permissions, AMBULANCE_AUTHORIZE_REQUIREMENT)


def _resolve_catalog_or_error(model, value_id, field_name, label):
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


def create_request(
    *,
    no_exp,
    pk_num,
    requesting_clinic_id,
    requested_by_name,
    requested_by_relationship_id=None,
    social_work_notes=None,
    reason_id,
    reason_notes=None,
    diagnosis_text=None,
    origin_street=None,
    origin_zip=None,
    origin_neighborhood=None,
    origin_borough=None,
    origin_phone=None,
    origin_reference=None,
    destination_id,
    schedules,
    actor_id,
    permissions=None,
):
    ensure_ambulance_write(permissions)

    if not CatClinica.objects.filter(pk=requesting_clinic_id).exists():
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"requestingClinicId": ["La clinica solicitante no existe."]},
        )

    reason = _resolve_catalog_or_error(CatMotivoTraslado, reason_id, "reasonId", "El motivo de traslado")
    destination = _resolve_catalog_or_error(CatDestinoAmbulancia, destination_id, "destinationId", "El destino")
    relationship = None
    if requested_by_relationship_id is not None:
        relationship = _resolve_catalog_or_error(
            Parentesco, requested_by_relationship_id, "requestedByRelationshipId", "El parentesco",
        )

    if reason.requires_notes and not (reason_notes or "").strip():
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"reasonNotes": ["Este motivo requiere especificar notas adicionales."]},
        )

    if not schedules:
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"schedules": ["Debes indicar al menos una fecha de traslado."]},
        )

    folio = f"AMB-{timezone.now().strftime('%Y%m%d%H%M%S')}-{no_exp}"

    with transaction.atomic():
        ambulance_request = AmbulanceRequestRepository.create(
            folio=folio,
            no_exp=no_exp,
            pk_num=pk_num or 0,
            requesting_clinic_id=requesting_clinic_id,
            requested_by_name=requested_by_name,
            requested_by_relationship=relationship,
            social_work_notes=social_work_notes,
            reason=reason,
            reason_notes=reason_notes,
            diagnosis_text=diagnosis_text,
            origin_street=origin_street,
            origin_zip=origin_zip,
            origin_neighborhood=origin_neighborhood,
            origin_borough=origin_borough,
            origin_phone=origin_phone,
            origin_reference=origin_reference,
            destination=destination,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )

        for index, schedule in enumerate(schedules):
            transfer_type = _resolve_catalog_or_error(
                CatTipoTraslado, schedule.get("transferTypeId"), "schedules", "El tipo de traslado",
            )
            service_type = _resolve_catalog_or_error(
                CatTipoServicioAmbulancia, schedule.get("serviceTypeId"), "schedules", "El tipo de servicio",
            )
            AmbulanceRequestRepository.add_schedule(
                request=ambulance_request,
                transfer_date=schedule["transferDate"],
                transfer_time=schedule["transferTime"],
                transfer_type=transfer_type,
                service_type=service_type,
                created_by_id=actor_id,
            )

    ambulance_request.refresh_from_db()
    return AmbulanceRequestRepository.to_contract(ambulance_request)


def _get_request_or_error(request_id):
    ambulance_request = AmbulanceRequestRepository.get_by_id(request_id)
    if ambulance_request is None:
        raise VisitDomainError("AMBULANCE_REQUEST_NOT_FOUND", "Solicitud no encontrada.", 404)
    return ambulance_request


def authorize_request(request_id, *, service_number, actor_id, permissions=None):
    ensure_ambulance_authorize(permissions)

    ambulance_request = _get_request_or_error(request_id)
    if ambulance_request.authorization_status != AmbulanceRequest.AuthorizationStatus.PENDIENTE:
        raise VisitDomainError(
            "AMBULANCE_REQUEST_ALREADY_RESOLVED", "La solicitud ya fue autorizada o rechazada.", 409,
        )
    if not (service_number or "").strip():
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"serviceNumber": ["Debes indicar el numero de servicio/ambulancia."]},
        )

    ambulance_request = AmbulanceRequestRepository.authorize(
        ambulance_request, service_number=service_number, updated_by_id=actor_id,
    )
    return AmbulanceRequestRepository.to_contract(ambulance_request)


def reject_request(request_id, *, notes, actor_id, permissions=None):
    ensure_ambulance_authorize(permissions)

    ambulance_request = _get_request_or_error(request_id)
    if ambulance_request.authorization_status != AmbulanceRequest.AuthorizationStatus.PENDIENTE:
        raise VisitDomainError(
            "AMBULANCE_REQUEST_ALREADY_RESOLVED", "La solicitud ya fue autorizada o rechazada.", 409,
        )
    if not (notes or "").strip():
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"notes": ["Debes indicar el motivo del rechazo."]},
        )

    ambulance_request = AmbulanceRequestRepository.reject(
        ambulance_request, notes=notes, updated_by_id=actor_id,
    )
    return AmbulanceRequestRepository.to_contract(ambulance_request)


def cancel_request(request_id, *, actor_id, permissions=None):
    ensure_ambulance_write(permissions)

    ambulance_request = _get_request_or_error(request_id)
    if ambulance_request.status == AmbulanceRequest.Status.BAJA:
        raise VisitDomainError("AMBULANCE_REQUEST_ALREADY_CANCELLED", "La solicitud ya esta dada de baja.", 409)

    ambulance_request = AmbulanceRequestRepository.cancel(ambulance_request, updated_by_id=actor_id)
    return AmbulanceRequestRepository.to_contract(ambulance_request)


def list_requests(*, permissions=None, **filters):
    ensure_ambulance_read(permissions)
    requests = AmbulanceRequestRepository.list_queryset(**filters)
    items = [AmbulanceRequestRepository.to_contract(r) for r in requests]
    return {"items": items, "total": len(items)}


def get_request_report(fecha_inicio, fecha_fin, *, permissions=None, **filters):
    ensure_ambulance_read(permissions)

    if fecha_inicio > fecha_fin:
        raise VisitDomainError(
            "VALIDATION_ERROR", "fechaInicio no puede ser posterior a fechaFin.", 422,
        )

    requests = AmbulanceRequestRepository.list_queryset(
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, **filters,
    )
    items = [AmbulanceRequestRepository.to_report_row(r) for r in requests]
    return {
        "items": items,
        "total": len(items),
        "fechaInicio": fecha_inicio,
        "fechaFin": fecha_fin,
    }
