"""Envio de notificaciones a usuarios.

`notificar(...)` corre dentro de la transaccion del llamador: crea la
notificacion (canal INTERNA, entregada al guardarse) y deja pendientes los
canales TIEMPO_REAL y CORREO, que salen DESPUES del commit para no avisar de
algo que se revirtio. El resultado de cada canal queda en ntf_entrega.
"""
from __future__ import annotations

from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.authentication.models import SyUsuario
from apps.authentication.services.audit_service import mask_email
from apps.realtime.models import RealtimeSequence
from apps.realtime.publisher import RealtimePublishMetadata, RealtimePublisher

from ..models import Entrega, Notificacion

EVENTO_TIEMPO_REAL = "notification.created"
SECUENCIA_TIEMPO_REAL = "notificaciones.stream"


def _siguiente_secuencia():
    with transaction.atomic():
        fila, _ = RealtimeSequence.objects.select_for_update().get_or_create(
            stream_key=SECUENCIA_TIEMPO_REAL, defaults={"last_sequence": 0},
        )
        fila.last_sequence += 1
        fila.save(update_fields=["last_sequence", "fch_modf"])
        return fila.last_sequence


def a_dict(notificacion: Notificacion) -> dict:
    return {
        "id": notificacion.pk,
        "categoria": notificacion.categoria,
        "titulo": notificacion.titulo,
        "cuerpo": notificacion.cuerpo,
        "tipoRecurso": notificacion.tipo_recurso,
        "referenciaRecurso": notificacion.referencia_recurso,
        "urlAccion": notificacion.url_accion,
        "prioridad": notificacion.prioridad,
        "fechaCreacion": notificacion.fecha_creacion.isoformat() if notificacion.fecha_creacion else None,
        "fechaLectura": notificacion.fecha_lectura.isoformat() if notificacion.fecha_lectura else None,
    }


def _registrar(entrega: Entrega, ok: bool, error: str | None = None):
    entrega.intentos += 1
    entrega.estatus = Entrega.Estatus.ENVIADA if ok else Entrega.Estatus.FALLIDA
    entrega.detalle_error = None if ok else (error or "")[:255]
    entrega.fecha_envio = timezone.now() if ok else entrega.fecha_envio
    entrega.save(update_fields=["intentos", "estatus", "detalle_error", "fecha_envio"])


def _publicar_tiempo_real(ids_notificacion):
    publicador = RealtimePublisher()
    for notificacion in Notificacion.objects.filter(pk__in=ids_notificacion):
        entrega = Entrega.objects.get(notificacion=notificacion, canal=Entrega.Canal.TIEMPO_REAL)
        try:
            peticion = str(uuid4())
            publicador.publish(
                group_names=[f"user.{notificacion.usuario_id}"],
                event_type=EVENTO_TIEMPO_REAL,
                entity="notification",
                entity_id=notificacion.pk,
                metadata=RealtimePublishMetadata(
                    request_id=peticion, correlation_id=peticion, sequence=_siguiente_secuencia(),
                ),
                payload=a_dict(notificacion),
            )
        except Exception as exc:  # canal secundario: se registra y no rompe el flujo
            _registrar(entrega, False, str(exc))
        else:
            _registrar(entrega, True)


def _encolar_correo(ids_notificacion):
    from ..tasks import enviar_correo_notificacion

    for id_notificacion in ids_notificacion:
        try:
            enviar_correo_notificacion.delay(id_notificacion)
        except Exception as exc:  # broker caido: queda FALLIDA para reintento manual
            entrega = Entrega.objects.filter(notificacion_id=id_notificacion, canal=Entrega.Canal.CORREO).first()
            if entrega:
                _registrar(entrega, False, f"No se pudo encolar: {exc}")


def notificar(
    ids_usuario,
    *,
    categoria: str,
    titulo: str,
    cuerpo: str,
    tipo_recurso: str,
    referencia_recurso: str,
    url_accion: str,
    prioridad: str = Notificacion.Prioridad.NORMAL,
    correo: bool = True,
    id_usuario_envio: int | None = None,
) -> list[Notificacion]:
    usuarios = {
        u.id_usuario: u
        for u in SyUsuario.objects.filter(pk__in=set(ids_usuario), est_activo=True).only("id_usuario", "correo")
    }
    creadas = []
    ahora = timezone.now()
    for id_usuario in dict.fromkeys(ids_usuario):
        usuario = usuarios.get(id_usuario)
        if usuario is None:
            continue
        notificacion = Notificacion.objects.create(
            usuario=usuario, categoria=categoria, titulo=titulo[:150], cuerpo=cuerpo[:500],
            tipo_recurso=tipo_recurso, referencia_recurso=referencia_recurso, url_accion=url_accion,
            prioridad=prioridad, id_usuario_envio=id_usuario_envio,
        )
        Entrega.objects.create(
            notificacion=notificacion, canal=Entrega.Canal.INTERNA,
            estatus=Entrega.Estatus.ENVIADA, intentos=1, fecha_envio=ahora,
        )
        Entrega.objects.create(notificacion=notificacion, canal=Entrega.Canal.TIEMPO_REAL)
        tiene_correo = correo and bool((usuario.correo or "").strip())
        Entrega.objects.create(
            notificacion=notificacion,
            canal=Entrega.Canal.CORREO,
            destino_enmascarado=mask_email(usuario.correo) if tiene_correo else None,
            estatus=Entrega.Estatus.PENDIENTE if tiene_correo else Entrega.Estatus.OMITIDA,
        )
        creadas.append(notificacion)

    ids = [n.pk for n in creadas]
    con_correo = list(
        Entrega.objects.filter(
            notificacion_id__in=ids, canal=Entrega.Canal.CORREO, estatus=Entrega.Estatus.PENDIENTE,
        ).values_list("notificacion_id", flat=True)
    )
    if ids:
        transaction.on_commit(lambda: _publicar_tiempo_real(ids))
    if con_correo:
        transaction.on_commit(lambda: _encolar_correo(con_correo))
    return creadas


MAX_INTENTOS_CORREO = 3


def reintentar_correos_fallidos(max_intentos: int = MAX_INTENTOS_CORREO) -> int:
    """Vuelve a encolar los correos FALLIDA con intentos disponibles (F7, cada hora).
    Cada envio suma un intento, asi que un correo que siempre falla se deja de
    reintentar al llegar al maximo y queda FALLIDA para revision."""
    ids = list(
        Entrega.objects.filter(
            canal=Entrega.Canal.CORREO, estatus=Entrega.Estatus.FALLIDA, intentos__lt=max_intentos,
        ).order_by("pk").values_list("notificacion_id", flat=True)
    )
    if ids:
        _encolar_correo(ids)
    return len(ids)


def listar(id_usuario, *, solo_no_leidas=False):
    consulta = Notificacion.objects.filter(usuario_id=id_usuario, fecha_archivo__isnull=True)
    if solo_no_leidas:
        consulta = consulta.filter(fecha_lectura__isnull=True)
    return consulta.order_by("-fecha_creacion", "-pk")


def contar_no_leidas(id_usuario) -> int:
    return listar(id_usuario, solo_no_leidas=True).count()


def marcar_leida(id_notificacion, id_usuario) -> Notificacion | None:
    notificacion = Notificacion.objects.filter(pk=id_notificacion, usuario_id=id_usuario).first()
    if notificacion and notificacion.fecha_lectura is None:
        notificacion.fecha_lectura = timezone.now()
        notificacion.save(update_fields=["fecha_lectura"])
    return notificacion


def marcar_todas_leidas(id_usuario) -> int:
    return listar(id_usuario, solo_no_leidas=True).update(fecha_lectura=timezone.now())
