from django.db import transaction

from apps.catalogos.models import Medicamentos
from apps.consulta_medica.models import PrescriptionAuthorization
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.prescription_authorization_repository import (
    PrescriptionAuthorizationRepository,
)
from apps.consulta_medica.repositories.prescription_item_repository import (
    PrescriptionItemRepository,
)
from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError

from .consultation_usecase import ensure_doctor_role

# Permiso separado del rol de doctor -- quien autoriza no necesariamente
# prescribe (mismo criterio que clinico:ambulancias:authorize, separado
# de clinico:ambulancias:write).
AUTHORIZE_PRESCRIPTION_PERMISSION_REQUIREMENT = {
    "allOf": ["clinico:recetas:authorize"]
}


def _ensure_authorize_role(roles, permissions=None):
    from apps.authentication.services.permission_dependencies import (
        evaluate_permission_requirement,
    )

    permission_state = evaluate_permission_requirement(
        AUTHORIZE_PRESCRIPTION_PERMISSION_REQUIREMENT, permissions or [],
    )
    if permission_state["granted"]:
        return

    raise VisitDomainError(
        "ROLE_NOT_ALLOWED",
        "No tenes permiso para autorizar recetas.",
        403,
    )


def _ensure_not_self_authorization(authorization, actor_id):
    """
    Segregacion de funciones: quien prescribio no puede autorizarse a si
    mismo, ni siquiera si tiene el permiso de autorizar (ej. un medico con
    doble rol). Mismo principio que el legado buscaba con
    `det_clinicas.pw_autoriza`, pero exigido de verdad en vez de confiar en
    que la persona no reingrese su propia contraseña.
    """
    if authorization.prescribed_by_id is not None and authorization.prescribed_by_id == actor_id:
        raise VisitDomainError(
            "SELF_AUTHORIZATION_NOT_ALLOWED",
            "No podes autorizar o rechazar una receta que vos mismo prescribiste.",
            403,
        )


def _maybe_create_authorization(prescription, visit):
    """
    Recalcula los conteos de la receta completa (items ACTIVOS) y crea una
    solicitud de autorizacion PENDIENTE si hace falta (al menos un
    medicamento ESPECIAL o controlado) y todavia no hay una pendiente --
    ver docstring de PrescriptionAuthorization.
    """
    items = PrescriptionItemRepository.list_for_prescription(prescription)

    medications_count = 0
    specialized_count = 0
    controlled_count = 0
    for item in items:
        medications_count += 1
        if item.medication.cuadro_basico == Medicamentos.CuadroBasico.ESPECIAL:
            specialized_count += 1
        if item.medication.is_controlled:
            controlled_count += 1

    requires_authorization = specialized_count > 0 or controlled_count > 0
    if not requires_authorization:
        return

    pending = PrescriptionAuthorizationRepository.get_pending_for_prescription(prescription)
    if pending is not None:
        # Ya hay una solicitud pendiente -- se actualiza para reflejar el
        # estado ACTUAL de la receta (el autorizador debe ver los
        # conteos vigentes, no un snapshot congelado del primer item que
        # disparo la solicitud).
        PrescriptionAuthorizationRepository.update_counts(
            pending,
            medications_count=medications_count,
            specialized_count=specialized_count,
            controlled_count=controlled_count,
        )
        return

    PrescriptionAuthorizationRepository.create(
        prescription,
        visit,
        prescribed_by_id=prescription.created_by_id,
        medications_count=medications_count,
        specialized_count=specialized_count,
        controlled_count=controlled_count,
    )


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


def add_prescription_item(
    visit_id,
    roles,
    *,
    medication_id,
    quantity,
    indications,
    dose=None,
    actor_id,
    permissions=None,
):
    """
    Agrega un item de receta estructurado (medicamento del catalogo +
    indicaciones + cantidad) -- complementa a save_prescriptions (texto
    libre). Equivalente moderno de det_receta del legado.
    """
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    _get_consultation_or_error(visit)

    medication = Medicamentos.objects.filter(pk=medication_id, is_active=True).first()
    if medication is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"medicationId": ["El medicamento no existe o no esta activo."]},
        )

    if medication.max_quantity and quantity > medication.max_quantity:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={
                "quantity": [
                    f"Maximo {medication.max_quantity} unidades para este medicamento."
                ]
            },
        )

    prescription = PrescriptionRepository.get_or_create_for_visit(
        visit, created_by_id=actor_id, updated_by_id=actor_id,
    )

    if PrescriptionItemRepository.get_active_by_prescription_and_medication(
        prescription, medication,
    ):
        raise VisitDomainError(
            "PRESCRIPTION_ITEM_ALREADY_EXISTS",
            "Ese medicamento ya esta agregado en la receta de esta consulta.",
            409,
        )

    normalized_indications = (indications or "").strip()
    if not normalized_indications:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"indications": ["Las indicaciones son obligatorias."]},
        )

    item = PrescriptionItemRepository.create(
        prescription=prescription,
        medication=medication,
        indications=normalized_indications,
        quantity=quantity,
        dose=(dose or "").strip() or None,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    _maybe_create_authorization(prescription, visit)
    return PrescriptionItemRepository.to_contract(item)


def cancel_prescription_item(visit_id, item_id, roles, *, actor_id, permissions=None, audit_hook):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    prescription = PrescriptionRepository.get_by_visit(visit)
    if prescription is None:
        raise VisitDomainError(
            "PRESCRIPTION_ITEM_NOT_FOUND", "Item de receta no encontrado.", 404,
        )

    item = PrescriptionItemRepository.get_by_id(item_id)
    if item is None or item.prescription_id != prescription.id_prescription:
        raise VisitDomainError(
            "PRESCRIPTION_ITEM_NOT_FOUND", "Item de receta no encontrado.", 404,
        )

    with transaction.atomic():
        # Gotcha A4.4: PrescriptionItemRepository.cancel muta la instancia en
        # memoria y devuelve el MISMO objeto -- datos_antes se captura ANTES.
        datos_antes = {
            "status": item.status,
            "medicationId": item.medication_id,
            "quantity": item.quantity,
        }
        item = PrescriptionItemRepository.cancel(item, updated_by_id=actor_id)
        audit_hook(
            resource_id=item.id_prescription_item,
            datos_antes=datos_antes,
            datos_despues={
                "status": item.status,
                "medicationId": item.medication_id,
                "quantity": item.quantity,
            },
            strict=True,
        )
    return PrescriptionItemRepository.to_contract(item)


def get_prescription_items(visit_id, roles, permissions=None):
    ensure_doctor_role(roles, permissions)

    visit = _get_visit_or_error(visit_id)
    prescription = PrescriptionRepository.get_by_visit(visit)
    if prescription is None:
        return {"items": [], "total": 0}

    items = PrescriptionItemRepository.list_for_prescription(prescription)
    contracts = [PrescriptionItemRepository.to_contract(item) for item in items]
    return {"items": contracts, "total": len(contracts)}


def list_pending_prescription_authorizations(roles, permissions=None):
    _ensure_authorize_role(roles, permissions)

    authorizations = PrescriptionAuthorizationRepository.list_pending()
    contracts = [PrescriptionAuthorizationRepository.to_contract(a) for a in authorizations]
    return {"items": contracts, "total": len(contracts)}


def list_prescription_authorizations_history(
    roles, permissions=None, *, status=None, date_from=None, date_to=None,
):
    """
    Historial de auditoria (cualquier estatus) -- trazabilidad NOM-024 de
    quien resolvio cada solicitud y cuando, a diferencia de
    list_pending_prescription_authorizations que solo muestra la cola
    activa. Mismo permiso que autorizar/rechazar.
    """
    _ensure_authorize_role(roles, permissions)

    if status is not None and status not in PrescriptionAuthorization.Status.values:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"status": ["Estatus invalido."]},
        )

    authorizations = PrescriptionAuthorizationRepository.list_history(
        status=status, date_from=date_from, date_to=date_to,
    )
    contracts = [PrescriptionAuthorizationRepository.to_contract(a) for a in authorizations]
    return {"items": contracts, "total": len(contracts)}


def authorize_prescription(authorization_id, roles, *, actor_id, permissions=None, audit_hook):
    _ensure_authorize_role(roles, permissions)

    authorization = PrescriptionAuthorizationRepository.get_by_id(authorization_id)
    if authorization is None:
        raise VisitDomainError("AUTHORIZATION_NOT_FOUND", "Autorizacion no encontrada.", 404)

    if authorization.status != authorization.Status.PENDIENTE:
        raise VisitDomainError(
            "AUTHORIZATION_ALREADY_RESOLVED",
            f'Esta autorizacion ya esta en estatus "{authorization.status}".',
            409,
        )

    _ensure_not_self_authorization(authorization, actor_id)

    with transaction.atomic():
        # Gotcha A4.4: PrescriptionAuthorizationRepository.authorize muta la
        # instancia en memoria y devuelve el MISMO objeto -- datos_antes se
        # captura ANTES.
        datos_antes = {
            "status": authorization.status,
            "authorizedById": authorization.authorized_by_id,
            "authorizedAt": (
                authorization.authorized_at.isoformat() if authorization.authorized_at else None
            ),
        }
        authorization = PrescriptionAuthorizationRepository.authorize(
            authorization, authorized_by_id=actor_id,
        )
        audit_hook(
            resource_id=authorization.id_authorization,
            datos_antes=datos_antes,
            datos_despues={
                "status": authorization.status,
                "authorizedById": authorization.authorized_by_id,
                "authorizedAt": (
                    authorization.authorized_at.isoformat() if authorization.authorized_at else None
                ),
                "prescribedById": authorization.prescribed_by_id,
                "medicationsCount": authorization.medications_count,
                "specializedCount": authorization.specialized_count,
                "controlledCount": authorization.controlled_count,
            },
            strict=True,
        )
    return PrescriptionAuthorizationRepository.to_contract(authorization)


def reject_prescription(authorization_id, roles, *, reason, actor_id, permissions=None, audit_hook):
    _ensure_authorize_role(roles, permissions)

    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"reason": ["El motivo de rechazo es obligatorio."]},
        )

    authorization = PrescriptionAuthorizationRepository.get_by_id(authorization_id)
    if authorization is None:
        raise VisitDomainError("AUTHORIZATION_NOT_FOUND", "Autorizacion no encontrada.", 404)

    if authorization.status != authorization.Status.PENDIENTE:
        raise VisitDomainError(
            "AUTHORIZATION_ALREADY_RESOLVED",
            f'Esta autorizacion ya esta en estatus "{authorization.status}".',
            409,
        )

    _ensure_not_self_authorization(authorization, actor_id)

    with transaction.atomic():
        # Gotcha A4.4: PrescriptionAuthorizationRepository.reject muta la
        # instancia en memoria y devuelve el MISMO objeto -- datos_antes se
        # captura ANTES.
        datos_antes = {
            "status": authorization.status,
            "authorizedById": authorization.authorized_by_id,
            "authorizedAt": (
                authorization.authorized_at.isoformat() if authorization.authorized_at else None
            ),
            "rejectionReason": authorization.rejection_reason,
        }
        authorization = PrescriptionAuthorizationRepository.reject(
            authorization, authorized_by_id=actor_id, reason=normalized_reason,
        )
        audit_hook(
            resource_id=authorization.id_authorization,
            datos_antes=datos_antes,
            datos_despues={
                "status": authorization.status,
                "authorizedById": authorization.authorized_by_id,
                "authorizedAt": (
                    authorization.authorized_at.isoformat() if authorization.authorized_at else None
                ),
                "rejectionReason": authorization.rejection_reason,
            },
            strict=True,
        )
    return PrescriptionAuthorizationRepository.to_contract(authorization)
