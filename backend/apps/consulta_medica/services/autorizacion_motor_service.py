"""Recetas <-> motor de autorizaciones (F5, plan autorizadores-medicos).

Adaptador del dominio de recetas: solo usa el contrato publico de
apps.autorizaciones (contracts + events), nunca sus modelos internos.

Interruptor AUTORIZACIONES_RECETAS_V2 (apagado por defecto):
- apagado: no se crea solicitud en el motor; todo funciona como antes;
- encendido: la autorizacion de receta crea/recalcula su solicitud y la
  decision del motor (autorizada/rechazada) se refleja en la receta.

Una receta con solicitud PENDIENTE en el motor ya no se decide desde la
pantalla anterior (409), aunque el interruptor se apague despues: asi el
motor y la receta nunca quedan en estados distintos. Si la visita no tiene
centro resoluble no se crea solicitud y la receta sigue el flujo anterior.
"""
from django.conf import settings

from apps.autorizaciones import contracts, events
from apps.catalogos.models import Medicamentos
from apps.consulta_medica.models import PrescriptionAuthorization
from apps.consulta_medica.repositories.prescription_authorization_repository import (
    PrescriptionAuthorizationRepository,
)
from apps.consulta_medica.repositories.prescription_item_repository import PrescriptionItemRepository
from apps.recepcion.services.errors import VisitDomainError

TIPO_ORIGEN = "RECETA"
CLAVE_TIPO = "REC"
MOTIVO_ESPECIAL = "MEDICAMENTO_ESPECIAL"
MOTIVO_CONTROLADO = "MEDICAMENTO_CONTROLADO"


def motor_activo() -> bool:
    return bool(getattr(settings, "AUTORIZACIONES_RECETAS_V2", False))


def _id_centro(visit):
    consultorio = visit.consultorio
    return getattr(consultorio, "id_center_id", None) if consultorio else None


def sincronizar_solicitud(authorization: PrescriptionAuthorization):
    """Crea o recalcula la solicitud del motor para una autorizacion PENDIENTE.
    Llamar dentro de la transaccion que crea/actualiza la autorizacion."""
    if not motor_activo() or authorization.status != PrescriptionAuthorization.Status.PENDIENTE:
        return None
    visit = authorization.visit
    prescription = authorization.prescription
    id_centro = _id_centro(visit)
    solicitante = authorization.prescribed_by_id or prescription.created_by_id
    if not id_centro or not solicitante:
        return None

    items, motivos = [], set()
    for item in PrescriptionItemRepository.list_for_prescription(prescription):
        medicamento = item.medication
        motivos_item = []
        if medicamento.cuadro_basico == Medicamentos.CuadroBasico.ESPECIAL:
            motivos_item.append(MOTIVO_ESPECIAL)
        if medicamento.is_controlled:
            motivos_item.append(MOTIVO_CONTROLADO)
        if not motivos_item:
            continue  # minimo necesario: solo lo que exige autorizacion
        motivos.update(motivos_item)
        items.append({
            "tipoItem": "MEDICAMENTO",
            "idItemOrigen": item.pk,
            "descripcion": medicamento.name,
            "cantidad": item.quantity,
            "motivo": motivos_item[-1],
        })
    if not items:
        return None

    return contracts.solicitar_autorizacion(
        clave_tipo=CLAVE_TIPO,
        id_origen=authorization.pk,
        id_centro=id_centro,
        id_usuario_solicitante=solicitante,
        items=items,
        motivos=sorted(motivos),
        folio_origen=prescription.folio,
        resumen_minimo={
            "medicamentos": authorization.medications_count,
            "especiales": authorization.specialized_count,
            "controlados": authorization.controlled_count,
        },
        id_paciente=getattr(visit, "patient_id", None),
    )


def asegurar_no_gestionada_por_motor(authorization: PrescriptionAuthorization):
    """La pantalla anterior no decide recetas que esperan en el motor. El detalle
    lleva el uuid de la solicitud para que la pantalla ofrezca ir a ella."""
    uuid_solicitud = contracts.uuid_solicitud_pendiente(TIPO_ORIGEN, authorization.pk)
    if uuid_solicitud:
        raise VisitDomainError(
            "AUTHORIZATION_MANAGED_BY_INBOX",
            "Esta receta se autoriza desde Solicitudes de autorización.",
            409,
            details={"solicitudUuid": str(uuid_solicitud)},
        )


def cancelar_solicitud(authorization: PrescriptionAuthorization, id_usuario):
    """La autorizacion de receta se cancelo (cascada de cancelacion de nota)."""
    contracts.cancelar_por_origen(TIPO_ORIGEN, authorization.pk, id_usuario=id_usuario)


def aplicar_resultado(evento: events.SolicitudResuelta):
    """Suscriptor: refleja en la receta la decision tomada en el motor (misma transaccion).
    Vencida o cancelada no cambian la receta: queda pendiente y no se puede surtir."""
    if evento.tipo_origen != TIPO_ORIGEN or evento.estatus not in ("AUTORIZADA", "RECHAZADA"):
        return
    authorization = (
        PrescriptionAuthorization.objects.select_for_update(of=("self",))
        .select_related("visit")
        .filter(pk=evento.id_origen, status=PrescriptionAuthorization.Status.PENDIENTE)
        .first()
    )
    if authorization is None:
        return
    if evento.estatus == "AUTORIZADA":
        PrescriptionAuthorizationRepository.authorize(authorization, authorized_by_id=evento.id_usuario_resolucion)
    else:
        motivo = evento.texto_motivo or "Rechazada en Solicitudes de autorización"
        PrescriptionAuthorizationRepository.reject(
            authorization, authorized_by_id=evento.id_usuario_resolucion, reason=motivo[:500],
        )


def conectar():
    events.suscribir("SolicitudResuelta", aplicar_resultado)
