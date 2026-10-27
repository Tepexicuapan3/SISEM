"""Envio de correo de una notificacion (Celery). Reutiliza la plantilla
institucional de authentication.send_notification_email_batch."""
from celery import shared_task
from django.conf import settings

from apps.authentication.services.email_service import send_notification_email_batch

from .models import Entrega, Notificacion
from .services.notificacion_service import _registrar


def _url_publica(ruta: str) -> str:
    base = getattr(settings, "SIRES_BASE_URL", None) or getattr(settings, "CITAS_BASE_URL", "")
    return f"{base.rstrip('/')}{ruta}"


@shared_task
def enviar_correo_notificacion(id_notificacion):
    notificacion = Notificacion.objects.select_related("usuario__detalle").filter(pk=id_notificacion).first()
    entrega = Entrega.objects.filter(notificacion_id=id_notificacion, canal=Entrega.Canal.CORREO).first()
    if notificacion is None or entrega is None or not notificacion.usuario.correo:
        return {"enviado": False}

    detalle = getattr(notificacion.usuario, "detalle", None)
    nombre = " ".join(filter(None, [getattr(detalle, "nombre", None), getattr(detalle, "paterno", None)])).strip()
    mensaje = (
        f"{notificacion.cuerpo}\n\n"
        f"Para revisarla inicia sesión en SIRES: {_url_publica(notificacion.url_accion)}\n\n"
        "Por seguridad, este correo no contiene información clínica y el enlace no autoriza "
        "nada por sí mismo: la decisión se toma dentro de SIRES y requiere confirmar tu contraseña."
    )
    try:
        resultado = send_notification_email_batch(
            [{"email": notificacion.usuario.correo, "name": nombre or notificacion.usuario.usuario,
              "username": notificacion.usuario.usuario}],
            notificacion.titulo,
            mensaje,
            "Autorizaciones médicas",
        )
    except Exception as exc:
        _registrar(entrega, False, str(exc))
        return {"enviado": False}

    ok = resultado.get("sent", 0) > 0
    _registrar(entrega, ok, None if ok else "El servidor de correo rechazó el envío")
    return {"enviado": ok}
