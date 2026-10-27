"""Pases de laboratorio y gabinete <-> motor de autorizaciones (F5).

Adaptador del dominio de pases: solo usa el contrato publico de
apps.autorizaciones (contracts + events).

Interruptor AUTORIZACIONES_PASES_V2 (apagado por defecto):
- apagado: no se crea solicitud; el pase queda NO_REQUIERE como hasta hoy;
- encendido: un pase de laboratorio o gabinete con algun estudio marcado
  (cat_estudiosmed.autorizado='S', el sw_autoriza del legado) crea su
  solicitud y queda PENDIENTE. El tipo sale del pase: laboratorio -> LAB,
  gabinete -> GAB (los estudios de imagen viajan en pases de gabinete).

Resultado del motor (misma transaccion): AUTORIZADA -> AUTORIZADO;
RECHAZADA -> RECHAZADO y se cancela SOLO el pase (con sus estudios), nunca
la nota; VENCIDA -> VENCIDO. Sin centro resoluble no se crea solicitud.
"""
from django.conf import settings

from apps.autorizaciones import contracts, events
from apps.pases.models import Referral
from apps.pases.repositories.referral_repository import ReferralRepository

ORIGEN_POR_TIPO = {
    Referral.ReferralType.LABORATORIO: ("PASE_LABORATORIO", "LAB"),
    Referral.ReferralType.GABINETE: ("PASE_GABINETE", "GAB"),
}
TIPOS_ORIGEN = {origen for origen, _ in ORIGEN_POR_TIPO.values()}
MOTIVO = "ESTUDIO_MARCADO"
ESTUDIO_MARCADO = "S"


def motor_activo() -> bool:
    return bool(getattr(settings, "AUTORIZACIONES_PASES_V2", False))


def _id_centro(visit):
    consultorio = visit.consultorio
    return getattr(consultorio, "id_center_id", None) if consultorio else None


def sincronizar_solicitud(referral: Referral, visit, *, id_usuario_solicitante):
    """Llamar dentro de la transaccion que crea el pase y sus estudios."""
    if not motor_activo() or referral.referral_type not in ORIGEN_POR_TIPO:
        return None
    id_centro = _id_centro(visit)
    if not id_centro or not id_usuario_solicitante:
        return None

    items = [
        {
            "tipoItem": "ESTUDIO",
            "idItemOrigen": detalle.pk,
            "descripcion": detalle.study_type.name,
            "cantidad": 1,
            "motivo": MOTIVO,
        }
        for detalle in referral.study_details.select_related("study_type").filter(is_active=True)
        if (detalle.study_type.is_authorized or "").strip().upper() == ESTUDIO_MARCADO
    ]
    if not items:
        return None

    tipo_origen, clave_tipo = ORIGEN_POR_TIPO[referral.referral_type]
    solicitud = contracts.solicitar_autorizacion(
        clave_tipo=clave_tipo,
        id_origen=referral.pk,
        id_centro=id_centro,
        id_usuario_solicitante=id_usuario_solicitante,
        items=items,
        motivos=[MOTIVO],
        folio_origen=referral.folio,
        resumen_minimo={"estudios": len(items)},
        id_paciente=getattr(referral, "patient_id", None) or getattr(visit, "patient_id", None),
    )
    referral.estatus_autorizacion = Referral.EstatusAutorizacion.PENDIENTE
    referral.save(update_fields=["estatus_autorizacion", "updated_at"])
    return solicitud


def cancelar_solicitud(referral: Referral, id_usuario):
    """El pase se cancelo (por el medico o por la cascada de cancelacion de nota)."""
    origen = ORIGEN_POR_TIPO.get(referral.referral_type)
    if origen:
        contracts.cancelar_por_origen(origen[0], referral.pk, id_usuario=id_usuario)


def aplicar_resultado(evento: events.SolicitudResuelta):
    if evento.tipo_origen not in TIPOS_ORIGEN:
        return
    nuevo = {
        "AUTORIZADA": Referral.EstatusAutorizacion.AUTORIZADO,
        "RECHAZADA": Referral.EstatusAutorizacion.RECHAZADO,
        "VENCIDA": Referral.EstatusAutorizacion.VENCIDO,
    }.get(evento.estatus)
    if nuevo is None:
        return
    referral = (
        Referral.objects.select_for_update()
        .filter(pk=evento.id_origen, estatus_autorizacion=Referral.EstatusAutorizacion.PENDIENTE)
        .first()
    )
    if referral is None:
        return
    referral.estatus_autorizacion = nuevo
    referral.save(update_fields=["estatus_autorizacion", "updated_at"])

    if nuevo == Referral.EstatusAutorizacion.RECHAZADO and referral.status == Referral.Status.ACTIVO:
        # Decision confirmada: el rechazo cancela solo el pase (y sus estudios), no la nota.
        for detalle in ReferralRepository.list_active_studies_for_update([referral.pk]):
            ReferralRepository.cancel_study_detail(detalle, updated_by_id=evento.id_usuario_resolucion)
        ReferralRepository.cancel(referral, cancellation_reason=None, updated_by_id=evento.id_usuario_resolucion)


def conectar():
    events.suscribir("SolicitudResuelta", aplicar_resultado)
