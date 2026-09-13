from django.db import transaction
from django.utils import timezone

from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.catalogos.models import CatCentroAtencion, Especialidades, EstudiosMed, MotivoCita
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.pases.models import Referral
from apps.pases.repositories.referral_repository import ReferralRepository
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_state_machine_usecase import ROLE_DOCTOR

# A diferencia de consultation_usecase.ensure_doctor_role (que usa un solo
# permiso -- clinico:consultas:read -- para lectura Y escritura, hueco de
# seguridad detectado en el gap analysis), pases separa lectura de
# escritura desde el arranque.
PASES_READ_REQUIREMENT = {"allOf": ["clinico:pases:read"]}
PASES_WRITE_REQUIREMENT = {"allOf": ["clinico:pases:create"]}

_STUDY_TYPES = {Referral.ReferralType.LABORATORIO, Referral.ReferralType.GABINETE}


def _ensure_permission(roles, permissions, requirement):
    normalized_roles = {(role or "").strip().upper() for role in roles}
    if ROLE_DOCTOR in normalized_roles:
        return

    state = evaluate_permission_requirement(requirement, permissions or [])
    if state["granted"]:
        return

    raise VisitDomainError(
        "ROLE_NOT_ALLOWED", "No tenes permiso para ejecutar esta accion.", 403,
    )


def ensure_pases_read(roles, permissions=None):
    _ensure_permission(roles, permissions, PASES_READ_REQUIREMENT)


def ensure_pases_write(roles, permissions=None):
    _ensure_permission(roles, permissions, PASES_WRITE_REQUIREMENT)


def get_referral_report(
    fecha_inicio,
    fecha_fin,
    roles,
    permissions=None,
    *,
    referral_type=None,
    status=None,
    no_exp=None,
):
    ensure_pases_read(roles, permissions)

    if fecha_inicio > fecha_fin:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "fechaInicio no puede ser posterior a fechaFin.",
            422,
        )

    referrals = ReferralRepository.list_report(
        fecha_inicio,
        fecha_fin,
        referral_type=referral_type,
        status=status,
        no_exp=no_exp,
    )
    items = [ReferralRepository.to_report_row(r) for r in referrals]

    return {
        "items": items,
        "total": len(items),
        "fechaInicio": fecha_inicio,
        "fechaFin": fecha_fin,
    }


def _get_visit_or_error(visit_id):
    visit = VisitRepository.get_by_id(visit_id)
    if not visit:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    return visit


def _get_consultation_or_error(visit):
    consultation = ConsultationRepository.get_by_visit(visit)
    if consultation is None:
        raise VisitDomainError(
            "CONSULTATION_NOT_FOUND",
            "Primero debes guardar el diagnostico de esta consulta.",
            409,
        )
    return consultation


def _resolve_fk_or_error(model, value_id, field_name, label):
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


def create_referral(
    visit_id,
    roles,
    *,
    referral_type,
    destination_center_id=None,
    specialty_id=None,
    requested_care=None,
    visit_type=None,
    studies=None,
    actor_id,
    permissions=None,
):
    ensure_pases_write(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    consultation = _get_consultation_or_error(visit)

    if ReferralRepository.get_active_by_consultation_and_type(consultation, referral_type):
        raise VisitDomainError(
            "REFERRAL_ALREADY_EXISTS",
            "Ya existe un pase activo de este tipo para esta consulta.",
            409,
        )

    destination_center = _resolve_fk_or_error(
        CatCentroAtencion, destination_center_id, "destinationCenterId", "El centro de destino",
    )
    specialty = _resolve_fk_or_error(
        Especialidades, specialty_id, "specialtyId", "La especialidad",
    )

    normalized_requested_care = (requested_care or "").strip() or None
    folio = f"REF-{timezone.now().strftime('%Y%m%d%H%M%S')}-{visit.no_exp}"

    with transaction.atomic():
        referral = ReferralRepository.create(
            consultation=consultation,
            no_exp=visit.no_exp,
            pk_num=visit.pk_num,
            referral_type=referral_type,
            destination_center=destination_center,
            specialty=specialty,
            requested_care=normalized_requested_care,
            visit_type=visit_type,
            folio=folio,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )

        if referral_type in _STUDY_TYPES:
            for index, study in enumerate(studies or []):
                study_type = _resolve_fk_or_error(
                    EstudiosMed,
                    study.get("studyTypeId"),
                    "studies",
                    "El estudio",
                )
                ReferralRepository.add_study_detail(
                    referral=referral,
                    study_type=study_type,
                    created_by_id=actor_id,
                    updated_by_id=actor_id,
                )

    referral.refresh_from_db()
    return ReferralRepository.to_contract(referral)


def cancel_referral(referral_id, roles, *, cancellation_reason_id, actor_id, permissions=None):
    ensure_pases_write(roles, permissions)

    referral = ReferralRepository.get_by_id(referral_id)
    if referral is None:
        raise VisitDomainError("REFERRAL_NOT_FOUND", "Pase no encontrado.", 404)

    if referral.status == Referral.Status.CANCELADO:
        raise VisitDomainError("REFERRAL_ALREADY_CANCELLED", "El pase ya esta cancelado.", 409)

    reason = (
        MotivoCita.objects.filter(pk=cancellation_reason_id, is_active=True)
        .exclude(aplica_a=MotivoCita.AplicaA.NO_ASISTIO)
        .first()
    )
    if reason is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={
                "cancellationReasonId": [
                    "El motivo no existe, no esta activo o no aplica a cancelacion."
                ]
            },
        )

    referral = ReferralRepository.cancel(
        referral, cancellation_reason=reason, updated_by_id=actor_id,
    )
    return ReferralRepository.to_contract(referral)


def get_patient_referrals(no_exp, pk_num, roles, permissions=None):
    ensure_pases_read(roles, permissions)

    referrals = ReferralRepository.list_for_patient(no_exp, pk_num)
    items = [ReferralRepository.to_contract(referral) for referral in referrals]
    return {"items": items, "total": len(items)}
