"""Cancelacion de una nota cerrada en cascada (change cancelacion-nota-cascada).

Flujo:
  FUERA del atomic (barato, sin locks): payload (422) -> permiso (403) ->
  visita/consulta (404) -> estado (409) -> autocancelacion (403) -> centro de
  la nota (422) -> `puede_cancelar_notas(actor, centro, hoy)` (403) ->
  reconciliacion RH de solo lectura -> re-autenticacion con contrasena propia
  (403 REAUTH_FAILED / 423 REAUTH_LOCKED / 503).

DENTRO de UN `transaction.atomic()`, con orden fijo de locks (todos por pk):
  1 Visit -> 2 VisitConsultation -> 3 VisitPrescription (solo ids, NO se carga
  `items`: json != jsonb) -> 4 items de receta activos -> 5 autorizaciones de
  receta pendientes -> 6 diagnosticos activos -> 7 pases activos -> 8 estudios
  de pase -> 9 incapacidades emitidas -> 10 resultados de estudio (lectura).
  Bloqueos 409: PRESCRIPTION_ITEM_DISPENSED, LEAVE_SENT_TO_RH,
  STUDY_RESULT_ACTIVE. Luego snapshot canonico -> hash -> cabecera -> cascada
  -> items de traza -> ChangeLog por entidad -> audit_hook (strict) ->
  `on_commit` realtime `visit.cancelled`.

Nunca DELETE. Nunca Oracle. La carrera con farmacia se serializa porque
`lock_items_for_dispense` bloquea las mismas filas de item.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.firma.verificador import VerificadorSimple
from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.catalogos.models import MotivoCancelacionNota
from apps.consulta_medica.models import (
    ChangeLog,
    ConsultationCancellationItem as Item,
    StudyResult,
    VisitConsultation,
    VisitDiagnosis,
    VisitPrescription,
    VisitPrescriptionItem,
)
# Designacion vieja o modulo de autorizadores, segun AUTORIZACIONES_NOTA_V2.
from apps.consulta_medica.services.autorizador_nota_service import puede_cancelar_notas
from apps.consulta_medica.repositories.consultation_cancellation_repository import (
    ConsultationCancellationRepository,
)
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.medical_leave_repository import MedicalLeaveRepository
from apps.consulta_medica.repositories.prescription_authorization_repository import (
    PrescriptionAuthorizationRepository,
)
from apps.consulta_medica.repositories.prescription_item_repository import (
    PrescriptionItemRepository,
)
from apps.consulta_medica.repositories.visit_diagnosis_repository import VisitDiagnosisRepository
from apps.consulta_medica.services.canonical_json import SCHEMA, canonical_json, sha256_hex
from apps.consulta_medica.services.change_log_service import build_key, record_change
from apps.consulta_medica.services.medical_leave_rh_reconciliation import find_folios_in_rh
from apps.consulta_medica.services import autorizacion_motor_service as motor
from apps.pases.repositories.referral_repository import ReferralRepository
from apps.pases.services import autorizacion_motor_service as motor_pases
from apps.realtime.events import publish_visit_cancelled
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_state_machine_usecase import (
    ROLE_AUTORIZADOR_NOTA,
    transition_visit_state,
)
from apps.consulta_medica.services.paciente_entrada import llave_publica

logger = logging.getLogger(__name__)

CANCEL_NOTE_PERMISSION_REQUIREMENT = {"allOf": ["clinico:notas:cancel"]}
MAX_DETAIL_LENGTH = 500

BLOCK_DISPENSED = "PRESCRIPTION_ITEM_DISPENSED"
BLOCK_LEAVE_RH = "LEAVE_SENT_TO_RH"
BLOCK_STUDY_RESULT = "STUDY_RESULT_ACTIVE"

_BLOCK_MESSAGES = {
    BLOCK_DISPENSED: "Hay medicamentos de la receta ya surtidos (total o parcialmente).",
    BLOCK_LEAVE_RH: "Hay una incapacidad enviada o verificada a RH.",
    BLOCK_STUDY_RESULT: "Hay resultados de estudio activos ligados a la consulta o a sus pases.",
}


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
def _ensure_cancel_permission(permissions):
    state = evaluate_permission_requirement(
        CANCEL_NOTE_PERMISSION_REQUIREMENT, permissions or [],
    )
    if not state["granted"]:
        raise VisitDomainError(
            "ROLE_NOT_ALLOWED", "No tenes permiso para cancelar notas.", 403,
        )


def _validate_payload(motivo_id, motivo_detalle, password=None, *, require_password=True):
    errors = {}
    if not isinstance(motivo_id, int) or isinstance(motivo_id, bool) or motivo_id <= 0:
        errors["motivoId"] = ["El motivo es obligatorio."]
    if motivo_detalle is not None:
        if not isinstance(motivo_detalle, str):
            errors["motivoDetalle"] = ["El detalle debe ser texto."]
        elif len(motivo_detalle) > MAX_DETAIL_LENGTH:
            errors["motivoDetalle"] = [f"Maximo {MAX_DETAIL_LENGTH} caracteres."]
    if require_password and (not isinstance(password, str) or not password):
        errors["password"] = ["La contrasena es obligatoria."]
    if errors:
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422, details=errors,
        )


def _ensure_not_self_cancellation(consultation, actor_id):
    """Segregacion de funciones: el medico de la nota no la cancela (mismo
    criterio que `_ensure_not_self_authorization` en prescription_item_usecase)."""
    if consultation.doctor_id is not None and consultation.doctor_id == actor_id:
        raise VisitDomainError(
            "SELF_AUTHORIZATION_NOT_ALLOWED",
            "No podes cancelar una nota de la que sos el medico tratante.",
            403,
        )


def _ensure_visit_cancellable_state(visit):
    if visit.status == "cancelada":
        raise VisitDomainError(
            "NOTE_ALREADY_CANCELLED", "La nota ya fue cancelada.", 409,
        )
    if visit.status != "cerrada":
        raise VisitDomainError(
            "VISIT_STATE_INVALID",
            "Solo se puede cancelar una nota con la consulta cerrada.",
            409,
        )


def _resolve_center_id(visit):
    consultorio = visit.consultorio
    center_id = getattr(consultorio, "id_center_id", None) if consultorio else None
    if not center_id:
        raise VisitDomainError(
            "NOTE_CENTER_UNRESOLVED",
            "No se pudo determinar el centro de atencion de la nota.",
            422,
        )
    return center_id


def _assignment_center_id(actor):
    try:
        return actor.detalle.id_centro_atencion_id
    except ObjectDoesNotExist:
        return None


def _load_visit_and_consultation(visit_id):
    visit = VisitRepository.get_by_id(visit_id)
    if visit is None:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    consultation = ConsultationRepository.get_by_visit(visit)
    if consultation is None:
        raise VisitDomainError(
            "CONSULTATION_NOT_FOUND", "La visita no tiene una consulta registrada.", 404,
        )
    return visit, consultation


# --------------------------------------------------------------------------- #
# Recoleccion de la cascada (con o sin locks)
# --------------------------------------------------------------------------- #
@dataclass
class Cascade:
    prescription_ids: list = field(default_factory=list)
    rx_items: list = field(default_factory=list)
    authorizations: list = field(default_factory=list)
    diagnoses: list = field(default_factory=list)
    referrals: list = field(default_factory=list)
    studies: list = field(default_factory=list)
    leaves: list = field(default_factory=list)
    study_result_ids: list = field(default_factory=list)

    def counts(self):
        return {
            "prescriptionItems": len(self.rx_items),
            "prescriptionAuthorizations": len(self.authorizations),
            "diagnoses": len(self.diagnoses),
            "referrals": len(self.referrals),
            "referralStudies": len(self.studies),
            "medicalLeaves": len(self.leaves),
        }


def _gather(visit, consultation, *, lock):
    """Reune las filas de la cascada. Con lock=True aplica el orden fijo de locks
    (debe estar dentro de transaction.atomic())."""
    cascade = Cascade()

    rx_qs = VisitPrescription.objects.filter(id_visit=visit).order_by("pk")
    if lock:
        rx_qs = rx_qs.select_for_update()
    # Solo ids: NO cargar `items` (JSONField) -- gotcha json != jsonb.
    cascade.prescription_ids = list(rx_qs.values_list("id_prescription", flat=True))

    item_qs = VisitPrescriptionItem.objects.filter(
        prescription_id__in=cascade.prescription_ids,
        status=VisitPrescriptionItem.Status.ACTIVO,
        is_active=True,
    ).order_by("pk")
    if lock:
        item_qs = item_qs.select_for_update()
    cascade.rx_items = list(item_qs)

    if lock:
        cascade.authorizations = (
            PrescriptionAuthorizationRepository.list_pending_for_prescription_for_update(
                cascade.prescription_ids
            )
        )
    else:
        from apps.consulta_medica.models import PrescriptionAuthorization as PA

        cascade.authorizations = list(
            PA.objects.filter(
                prescription_id__in=cascade.prescription_ids, status=PA.Status.PENDIENTE,
            ).order_by("pk")
        )

    dx_qs = VisitDiagnosis.objects.filter(
        consultation=consultation, status=VisitDiagnosis.Status.ACTIVO, is_active=True,
    ).order_by("pk")
    if lock:
        dx_qs = dx_qs.select_for_update()
    cascade.diagnoses = list(dx_qs)

    if lock:
        cascade.referrals = ReferralRepository.list_active_for_consultation_for_update(
            consultation
        )
        cascade.studies = ReferralRepository.list_active_studies_for_update(
            [r.pk for r in cascade.referrals]
        )
        cascade.leaves = MedicalLeaveRepository.list_active_for_consultation_for_update(
            consultation
        )
    else:
        from apps.consulta_medica.models import MedicalLeave
        from apps.pases.models import Referral, ReferralStudyDetail

        cascade.referrals = list(
            Referral.objects.filter(
                consultation=consultation, status=Referral.Status.ACTIVO, is_active=True,
            ).order_by("pk")
        )
        cascade.studies = list(
            ReferralStudyDetail.objects.filter(
                referral_id__in=[r.pk for r in cascade.referrals],
                status=Referral.Status.ACTIVO, is_active=True,
            ).order_by("pk")
        )
        cascade.leaves = list(
            MedicalLeave.objects.filter(
                consultation=consultation, is_active=True,
                status=MedicalLeave.Status.EMITIDA,
            ).order_by("pk")
        )

    # 10. Resultados de estudio activos (lectura; ligados a la consulta o a
    # estudios de sus pases).
    cascade.study_result_ids = sorted(
        set(
            StudyResult.objects.filter(is_active=True)
            .filter(
                Q(consultation=consultation)
                | Q(referral_study__referral__consultation=consultation)
            )
            .values_list("id_study_result", flat=True)
        )
    )
    return cascade


def _leave_is_sent_to_rh(leave, rh_folios):
    from apps.consulta_medica.models import MedicalLeave

    if leave.rh_status in (MedicalLeave.RhStatus.ENVIADA, MedicalLeave.RhStatus.VERIFICADA):
        return True
    return leave.folio in rh_folios


def _find_blockers(cascade, rh_folios):
    blockers = []
    dispensed = [i.pk for i in cascade.rx_items if (i.dispensed_quantity or 0) > 0]
    if dispensed:
        blockers.append({"code": BLOCK_DISPENSED, "message": _BLOCK_MESSAGES[BLOCK_DISPENSED], "ids": dispensed})
    sent = [l.pk for l in cascade.leaves if _leave_is_sent_to_rh(l, rh_folios)]
    if sent:
        blockers.append({"code": BLOCK_LEAVE_RH, "message": _BLOCK_MESSAGES[BLOCK_LEAVE_RH], "ids": sent})
    if cascade.study_result_ids:
        blockers.append({
            "code": BLOCK_STUDY_RESULT, "message": _BLOCK_MESSAGES[BLOCK_STUDY_RESULT],
            "ids": list(cascade.study_result_ids),
        })
    return blockers


def _raise_blockers(blockers):
    first = blockers[0]
    raise VisitDomainError(
        first["code"], first["message"], 409, details={"blockers": blockers},
    )


# --------------------------------------------------------------------------- #
# Snapshot canonico del estado ANTERIOR
# --------------------------------------------------------------------------- #
def _build_snapshot(*, visit, consultation, motivo, motivo_detalle, actor_id, decision,
                    center_id, outside_assignment, cascade):
    items = []
    for dx in cascade.diagnoses:
        items.append({"type": Item.EntityType.DIAGNOSIS, "id": dx.pk, "status": dx.status,
                      "cie": dx.cie_id, "notes": dx.notes})
    for rx in cascade.rx_items:
        items.append({"type": Item.EntityType.RX_ITEM, "id": rx.pk, "status": rx.status,
                      "medicationId": rx.medication_id, "quantity": rx.quantity,
                      "dispensedQuantity": rx.dispensed_quantity, "dose": rx.dose,
                      "indications": rx.indications, "prescriptionId": rx.prescription_id})
    for auth in cascade.authorizations:
        items.append({"type": Item.EntityType.RX_AUTH, "id": auth.pk, "status": auth.status,
                      "prescriptionId": auth.prescription_id})
    for ref in cascade.referrals:
        items.append({"type": Item.EntityType.REFERRAL, "id": ref.pk, "status": ref.status,
                      "referralType": ref.referral_type, "folio": ref.folio})
    for study in cascade.studies:
        items.append({"type": Item.EntityType.REFERRAL_STUDY, "id": study.pk,
                      "status": study.status, "referralId": study.referral_id,
                      "studyTypeId": study.study_type_id})
    for leave in cascade.leaves:
        items.append({"type": Item.EntityType.MEDICAL_LEAVE, "id": leave.pk,
                      "status": leave.status, "rhStatus": leave.rh_status,
                      "folio": leave.folio, "days": leave.days,
                      "startDate": leave.start_date, "endDate": leave.end_date})
    items.sort(key=lambda row: (row["type"], row["id"]))

    autorizador = {
        "id": actor_id, "designationId": decision.designacion_id,
        "scope": decision.alcance_aplicado, "outsideAssignment": outside_assignment,
    }
    if decision.id_autorizador_tipo is not None:  # solo con AUTORIZACIONES_NOTA_V2
        autorizador["authorizerTypeId"] = decision.id_autorizador_tipo
    return {
        "schema": SCHEMA,
        "visit": {"id": visit.id_visit, "folio": visit.folio, "status": visit.status,
                  "noExp": llave_publica(visit)[0], "pkNum": llave_publica(visit)[1]},
        "consultation": {
            "id": consultation.pk, "doctorId": consultation.doctor_id,
            "primaryDiagnosis": consultation.primary_diagnosis,
            "cie": consultation.cie_id, "finalNote": consultation.final_note,
        },
        "motivo": {"id": motivo.pk, "name": motivo.name, "detail": motivo_detalle},
        "autorizador": autorizador,
        "centro": {"id": center_id},
        "items": items,
    }


# --------------------------------------------------------------------------- #
# Casos de uso
# --------------------------------------------------------------------------- #
def get_cancellation_preview(visit_id, actor, permissions):
    """GET cancellation-preview: que pasaria si se cancela (sin tocar nada)."""
    _ensure_cancel_permission(permissions)
    visit, consultation = _load_visit_and_consultation(visit_id)
    actor_id = actor.id_usuario

    already = ConsultationCancellationRepository.get_for_consultation(consultation.pk)
    state_ok = visit.status == "cerrada" and already is None
    cascade = _gather(visit, consultation, lock=False)
    rh_folios = find_folios_in_rh([l.folio for l in cascade.leaves])
    blockers = _find_blockers(cascade, rh_folios)

    center_id = None
    can_authorize = False
    reason = None
    outside = False
    try:
        center_id = _resolve_center_id(visit)
    except VisitDomainError as exc:
        reason = exc.code
    if center_id is not None:
        decision = puede_cancelar_notas(actor_id, center_id, timezone.localdate())
        can_authorize = bool(decision)
        reason = None if can_authorize else "AUTHORIZER_NOT_DESIGNATED"
        outside = _assignment_center_id(actor) != center_id

    is_self = consultation.doctor_id is not None and consultation.doctor_id == actor_id
    return {
        "cancelable": bool(state_ok and not blockers and can_authorize and not is_self),
        "visitStatus": visit.status,
        "alreadyCancelled": already is not None or visit.status == "cancelada",
        "blockers": blockers,
        "cascade": cascade.counts(),
        "puedeAutorizar": can_authorize,
        "puedeAutorizarMotivo": reason,
        "autoCancelacion": is_self,
        "fueraAdscripcion": outside,
        "centroId": center_id,
    }


def get_cancellation(visit_id, permissions):
    """GET cancellation: cabecera de la cancelacion (o 404)."""
    _ensure_cancel_permission(permissions)
    visit = VisitRepository.get_by_id(visit_id)
    if visit is None:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    cancellation = ConsultationCancellationRepository.get_by_visit(visit.id_visit)
    if cancellation is None:
        raise VisitDomainError(
            "CANCELLATION_NOT_FOUND", "La nota no tiene una cancelacion registrada.", 404,
        )
    payload = ConsultationCancellationRepository.to_contract(cancellation)
    payload["items"] = [
        {"entityType": i.entity_type, "entityId": i.entity_id,
         "previousStatus": i.previous_status, "newStatus": i.new_status}
        for i in ConsultationCancellationRepository.list_items(cancellation.pk)
    ]
    return payload


def cancel_consultation(
    visit_id,
    actor,
    permissions,
    *,
    motivo_id,
    motivo_detalle=None,
    password,
    audit_hook,
    request_id=None,
    verifier=None,
):
    """Cancela en cascada una nota cerrada. `actor` es el SyUsuario autenticado."""
    # --- FUERA del atomic -------------------------------------------------
    _validate_payload(motivo_id, motivo_detalle, password)
    _ensure_cancel_permission(permissions)
    actor_id = actor.id_usuario

    visit, consultation = _load_visit_and_consultation(visit_id)
    _ensure_visit_cancellable_state(visit)
    _ensure_not_self_cancellation(consultation, actor_id)

    motivo = MotivoCancelacionNota.objects.filter(pk=motivo_id, is_active=True).first()
    if motivo is None:
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"motivoId": ["El motivo no existe o no esta activo."]},
        )

    center_id = _resolve_center_id(visit)
    decision = puede_cancelar_notas(actor_id, center_id, timezone.localdate())
    if not decision:
        raise VisitDomainError(
            "AUTHORIZER_NOT_DESIGNATED",
            "No tenes una designacion vigente para cancelar notas en este centro.",
            403,
        )
    outside_assignment = _assignment_center_id(actor) != center_id

    # Lectura de solo lectura contra la replica de RH, FUERA del atomic: una
    # BD externa lenta no debe sostener locks de la transaccion principal.
    pre_cascade = _gather(visit, consultation, lock=False)
    rh_folios = find_folios_in_rh([l.folio for l in pre_cascade.leaves])

    signer = verifier or VerificadorSimple()
    try:
        signature = signer.verificar(
            actor, password, f"cancelacion-nota:visit={visit.id_visit}".encode("utf-8"),
        )
    except AuthServiceError as exc:
        raise VisitDomainError(exc.code, exc.message, exc.status_code, details=exc.details)

    # --- DENTRO del atomic (orden fijo de locks) --------------------------
    with transaction.atomic():
        locked_visit = VisitRepository.get_for_update(visit.id_visit)
        if locked_visit is None:
            raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
        _ensure_visit_cancellable_state(locked_visit)

        locked_consultation = (
            VisitConsultation.objects.select_for_update().filter(pk=consultation.pk).first()
        )
        if locked_consultation is None:
            raise VisitDomainError("CONSULTATION_NOT_FOUND", "Consulta no encontrada.", 404)
        if ConsultationCancellationRepository.get_for_consultation(locked_consultation.pk):
            raise VisitDomainError(
                "NOTE_ALREADY_CANCELLED", "La nota ya fue cancelada.", 409,
            )

        cascade = _gather(locked_visit, locked_consultation, lock=True)
        blockers = _find_blockers(cascade, rh_folios)
        if blockers:
            _raise_blockers(blockers)

        snapshot = _build_snapshot(
            visit=locked_visit, consultation=locked_consultation, motivo=motivo,
            motivo_detalle=motivo_detalle, actor_id=actor_id, decision=decision,
            center_id=center_id, outside_assignment=outside_assignment, cascade=cascade,
        )
        snapshot_text = canonical_json(snapshot)
        content_hash = sha256_hex(snapshot_text)

        cancellation = ConsultationCancellationRepository.create_header(
            consultation=locked_consultation, visit=locked_visit, reason=motivo,
            reason_detail=motivo_detalle, authorizer=actor,
            designation_id=decision.designacion_id,
            authorizer_record_id=decision.id_autorizador,
            authorizer_type_id=decision.id_autorizador_tipo,
            applied_scope=decision.alcance_aplicado or "", center_id=center_id,
            outside_assignment=outside_assignment, signature_method=signature.metodo,
            canonical_snapshot=snapshot_text, content_hash=content_hash,
            signed_at=signature.firmado_en,
        )

        trace = []  # (type, id, previous, new, table, pk_column)

        def _cancel(entity_type, obj, new_status, action):
            previous = obj.status
            action()
            trace.append((entity_type, obj.pk, previous, new_status, obj._meta))

        for rx in cascade.rx_items:
            _cancel(Item.EntityType.RX_ITEM, rx, "cancelado",
                    lambda rx=rx: PrescriptionItemRepository.cancel(rx, updated_by_id=actor_id))
        for auth in cascade.authorizations:
            _cancel(Item.EntityType.RX_AUTH, auth, "cancelada",
                    lambda auth=auth: PrescriptionAuthorizationRepository.cancel(auth))
            # Motor de autorizaciones: su solicitud pendiente (si existe) tambien se cancela.
            motor.cancelar_solicitud(auth, actor_id)
        for dx in cascade.diagnoses:
            _cancel(Item.EntityType.DIAGNOSIS, dx, "cancelado",
                    lambda dx=dx: VisitDiagnosisRepository.cancel(dx, updated_by_id=actor_id))
        for ref in cascade.referrals:
            # cancellation_reason NULL: la traza vive en la cancelacion de nota.
            _cancel(Item.EntityType.REFERRAL, ref, "cancelado",
                    lambda ref=ref: ReferralRepository.cancel(
                        ref, cancellation_reason=None, updated_by_id=actor_id))
            # Motor de autorizaciones: la solicitud pendiente del pase tambien se cancela.
            motor_pases.cancelar_solicitud(ref, actor_id)
        for study in cascade.studies:
            _cancel(Item.EntityType.REFERRAL_STUDY, study, "cancelado",
                    lambda study=study: ReferralRepository.cancel_study_detail(
                        study, updated_by_id=actor_id))
        for leave in cascade.leaves:
            _cancel(Item.EntityType.MEDICAL_LEAVE, leave, "cancelada",
                    lambda leave=leave: MedicalLeaveRepository.cancel(
                        leave, cancelled_by_id=actor_id))

        # Visita cerrada -> cancelada por la maquina de estados (rol interno).
        previous_visit_status = locked_visit.status
        transition_visit_state(
            previous_visit_status, "cancelada", ROLE_AUTORIZADOR_NOTA, motivo=motivo,
        )
        VisitRepository.update_status(locked_visit, "cancelada")
        VisitRepository.log_status_change(
            locked_visit, previous_visit_status, "cancelada", changed_by_id=actor_id,
            notes=f"NOTA CANCELADA #{cancellation.pk}",
        )
        trace.append((Item.EntityType.VISIT, locked_visit.pk, previous_visit_status,
                      "cancelada", locked_visit._meta))

        ConsultationCancellationRepository.add_items(
            cancellation, [(t, i, prev, new) for t, i, prev, new, _ in trace],
        )
        for _type, entity_id, prev, new, meta in trace:
            record_change(
                table=meta.db_table, key=build_key(meta.pk.column, entity_id),
                action=ChangeLog.Action.UPDATE, reason=ChangeLog.Reason.NOTE_CANCELLATION,
                user=actor_id, previous={"status": prev}, new={"status": new},
            )

        audit_hook(
            resource_id=cancellation.pk,
            datos_antes={"visitStatus": previous_visit_status},
            datos_despues={"visitStatus": "cancelada", "cascade": cascade.counts()},
            meta={
                "visitId": locked_visit.id_visit,
                "fueraAdscripcion": outside_assignment,
                "alcance": decision.alcance_aplicado,
                "hash": content_hash,
            },
            strict=True,
        )

        visit_pk, cancellation_pk = locked_visit.id_visit, cancellation.pk
        transaction.on_commit(
            lambda: _publish_cancelled(visit_pk, previous_visit_status, cancellation_pk, request_id)
        )

    return {
        "cancellationId": cancellation.pk,
        "visit": {"id": locked_visit.id_visit, "status": locked_visit.status},
        "hashContenido": content_hash,
        "metodoFirma": signature.metodo,
        "fueraAdscripcion": outside_assignment,
        "cascade": cascade.counts(),
    }


def _publish_cancelled(visit_id, previous_status, cancellation_id, request_id):
    try:
        publish_visit_cancelled(
            visit_id=visit_id, status="cancelada", previous_status=previous_status,
            request_id=request_id, correlation_id=request_id,
            note_cancellation_id=cancellation_id,
        )
    except Exception:  # noqa: BLE001 - el evento nunca revierte lo ya commiteado
        logger.exception(
            "No se pudo publicar evento realtime de cancelacion de nota",
            extra={"visit_id": visit_id, "request_id": request_id},
        )
