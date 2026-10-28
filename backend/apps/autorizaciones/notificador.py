"""Quien se entera de que en el flujo de autorizacion (suscriptor de eventos).

Las notificaciones solo dicen folio, tipo, centro y fecha; nunca el paciente
ni los medicamentos o estudios. El enlace lleva al detalle, donde se vuelve
a validar todo y se pide confirmar con contraseña.
"""
from django.utils import timezone

from apps.notificaciones.services import notificacion_service

from . import events
from .models import Autorizador, Solicitud, SolicitudDestinatario
from .repositories.autorizador_repository import AutorizadorRepository

TIPO_RECURSO = "solicitud_autorizacion"
TIPO_RECURSO_AUTORIZADOR = "autorizador"
RUTA_ADMIN_AUTORIZADORES = "/admin/autorizacion/autorizadores"
RUTA_BANDEJA = "/clinico/autorizaciones"


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


def al_escalar(evento: events.SolicitudEscalada):
    solicitud = _solicitud(evento.id_solicitud)
    _enviar(_usuarios_de(evento.ids_autorizador_recordatorio), solicitud, "AUT_RECORDATORIO",
            f"Recordatorio: la solicitud {solicitud.folio} sigue pendiente")
    _enviar(_usuarios_de(evento.ids_autorizador_nuevos), solicitud, "AUT_SOLICITADA",
            "Solicitud de autorización pendiente")
    if evento.sin_elegibles:
        _enviar(
            [solicitud.id_usuario_solicitante], solicitud, "AUT_SIN_ELEGIBLES",
            f"Nadie ha podido atender tu solicitud {solicitud.folio}",
            cuerpo=f"{_cuerpo(solicitud)}. No hay autorizadores vigentes que cubran este tipo y centro; "
                   "avisa al área responsable.",
        )


def _avisar_vigencia(evento, categoria, titulo_autorizador, titulo_admin, verbo):
    fecha = evento.fecha_fin_vigencia.strftime("%d/%m/%Y")
    comun = dict(
        categoria=categoria, tipo_recurso=TIPO_RECURSO_AUTORIZADOR,
        referencia_recurso=str(evento.id_autorizador),
    )
    notificacion_service.notificar(
        [evento.id_usuario], titulo=titulo_autorizador,
        cuerpo=f"Tu designación como autorizador {verbo} el {fecha}. Solicita la renovación al área responsable.",
        url_accion=RUTA_BANDEJA, **comun,
    )
    administradores = [i for i in AutorizadorRepository.ids_usuarios_que_renuevan() if i != evento.id_usuario]
    if administradores:
        usuario = AutorizadorRepository.base_queryset().get(pk=evento.id_autorizador).usuario
        nombre = getattr(getattr(usuario, "detalle", None), "nombre_completo", None) or usuario.usuario
        notificacion_service.notificar(
            administradores, titulo=titulo_admin,
            cuerpo=f"La designación de {nombre} {verbo} el {fecha}. Puedes renovarla en Autorizadores médicos.",
            url_accion=RUTA_ADMIN_AUTORIZADORES, **comun,
        )


def al_por_vencer(evento: events.AutorizadorPorVencer):
    _avisar_vigencia(evento, "AUT_AUTORIZADOR_POR_VENCER", "Tu designación como autorizador está por vencer",
                     "Autorizador por vencer", "vence")


def al_vencer(evento: events.AutorizadorVencido):
    _avisar_vigencia(evento, "AUT_AUTORIZADOR_VENCIDO", "Tu designación como autorizador venció",
                     "Autorizador vencido", "venció")


def registrar():
    events.suscribir("SolicitudCreada", al_crear)
    events.suscribir("SolicitudEnviada", al_enviar)
    events.suscribir("SolicitudResuelta", al_resolver)
    events.suscribir("SolicitudEscalada", al_escalar)
    events.suscribir("AutorizadorPorVencer", al_por_vencer)
    events.suscribir("AutorizadorVencido", al_vencer)
