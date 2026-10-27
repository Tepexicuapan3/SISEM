"""Quien se entera de que en el flujo de autorizacion (suscriptor de eventos).

Las notificaciones solo dicen folio, tipo, centro y fecha; nunca el paciente
ni los medicamentos o estudios. El enlace lleva al detalle, donde se vuelve
a validar todo y se pide confirmar con contraseña.
"""
from django.utils import timezone

from apps.notificaciones.services import notificacion_service

from . import events
from .models import Autorizador, Solicitud, SolicitudDestinatario

TIPO_RECURSO = "solicitud_autorizacion"


def _solicitud(id_solicitud):
    return Solicitud.objects.select_related("tipo_autorizacion", "centro_atencion", "motivo_cierre").get(pk=id_solicitud)


def _cuerpo(solicitud):
    fecha = timezone.localtime(solicitud.fecha_creacion).strftime("%d/%m/%Y %H:%M")
    return (
        f"{solicitud.folio} · {solicitud.tipo_autorizacion.nombre} · "
        f"{solicitud.centro_atencion.name} ({solicitud.clues}) · {fecha}"
    )


def _enviar(ids_usuario, solicitud, categoria, titulo, *, cuerpo=None, id_usuario_envio=None):
    if not ids_usuario:
        return
    notificacion_service.notificar(
        ids_usuario,
        categoria=categoria,
        titulo=titulo,
        cuerpo=cuerpo or _cuerpo(solicitud),
        tipo_recurso=TIPO_RECURSO,
        referencia_recurso=str(solicitud.uuid_publico),
        # Ruta del frontend (area clinica): el detalle es el destino del boton.
        url_accion=f"/clinico/autorizaciones/{solicitud.uuid_publico}",
        prioridad=solicitud.prioridad,
        id_usuario_envio=id_usuario_envio,
    )


def _usuarios_de(ids_autorizador):
    return list(Autorizador.objects.filter(pk__in=ids_autorizador).values_list("usuario_id", flat=True))


def _usuarios_destinatarios(solicitud, estatus=None):
    consulta = SolicitudDestinatario.objects.filter(solicitud=solicitud)
    if estatus:
        consulta = consulta.filter(estatus__in=estatus)
    return list(consulta.values_list("autorizador__usuario_id", flat=True))


def al_crear(evento: events.SolicitudCreada):
    solicitud = _solicitud(evento.id_solicitud)
    _enviar(_usuarios_de(evento.ids_autorizador_destinatarios), solicitud, "AUT_SOLICITADA",
            "Solicitud de autorización pendiente")
    if solicitud.sin_elegibles:
        _enviar(
            [solicitud.id_usuario_solicitante], solicitud, "AUT_SIN_ELEGIBLES",
            "No hay autorizadores disponibles para tu solicitud",
            cuerpo=f"{_cuerpo(solicitud)}. Ningún autorizador vigente cubre este tipo y centro; "
                   "avisa al área responsable para asignarlo.",
        )


def al_enviar(evento: events.SolicitudEnviada):
    _enviar(_usuarios_de(evento.ids_autorizador), _solicitud(evento.id_solicitud), "AUT_SOLICITADA",
            "Solicitud de autorización pendiente", id_usuario_envio=evento.id_usuario_envio)


def al_resolver(evento: events.SolicitudResuelta):
    solicitud = _solicitud(evento.id_solicitud)
    if evento.estatus in (Solicitud.Estatus.AUTORIZADA, Solicitud.Estatus.RECHAZADA):
        resultado = "autorizada" if evento.estatus == Solicitud.Estatus.AUTORIZADA else "rechazada"
        motivo = f" Motivo: {solicitud.motivo_cierre.descripcion}." if solicitud.motivo_cierre_id else ""
        _enviar([solicitud.id_usuario_solicitante], solicitud, "AUT_RESUELTA",
                f"Solicitud {solicitud.folio} {resultado}", cuerpo=f"{_cuerpo(solicitud)}.{motivo}")
        _enviar(
            _usuarios_destinatarios(solicitud, [SolicitudDestinatario.Estatus.ATENDIDA_POR_OTRO]),
            solicitud, "AUT_ATENDIDA_POR_OTRO", f"Solicitud {solicitud.folio} ya fue atendida",
        )
    elif evento.estatus == Solicitud.Estatus.VENCIDA:
        _enviar([solicitud.id_usuario_solicitante, *_usuarios_destinatarios(solicitud)], solicitud,
                "AUT_VENCIDA", f"Solicitud {solicitud.folio} vencida sin resolverse")
    elif evento.estatus == Solicitud.Estatus.CANCELADA:
        _enviar(_usuarios_destinatarios(solicitud), solicitud, "AUT_CANCELADA",
                f"Solicitud {solicitud.folio} cancelada")


def registrar():
    events.suscribir("SolicitudCreada", al_crear)
    events.suscribir("SolicitudEnviada", al_enviar)
    events.suscribir("SolicitudResuelta", al_resolver)
