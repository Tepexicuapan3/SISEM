import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import SesionUsuario
from apps.authentication.services.errors import PolicyStoreUnavailableError
from apps.authentication.services.session_registry import start_session

logger = logging.getLogger(__name__)
policy_store = PolicyStore()


def revoke_user_sessions(user, reason=SesionUsuario.CierrePor.REVOCADA) -> bool:
    # Revoca todas las sesiones del usuario. Retorna True si Redis quedo limpio.
    # Orden: 1) filas DB, 2) Redis, 3) WS. Cerrar las filas primero evita la
    # carrera con el barrido de sesiones abandonadas (tasks.py).
    SesionUsuario.objects.filter(usuario=user, fch_fin__isnull=True).update(
        fch_fin=timezone.now(), cerrada_por=reason
    )

    redis_ok = True
    try:
        policy_store.clear_active_session(user.id_usuario)
    except PolicyStoreUnavailableError:
        # Fail-soft: no bloquea la accion admin, las filas DB ya se cerraron.
        redis_ok = False
        logger.warning(
            "SESSION_REVOKE_REDIS_UNAVAILABLE user_id=%s", user.id_usuario
        )

    _notify_session_revoked(user.id_usuario)
    return redis_ok


def rotate_user_session(user, ip_address, user_agent):
    # Cierra las sesiones vigentes y abre una nueva (tokens frescos).
    revoke_user_sessions(user)
    return start_session(user, ip_address, user_agent)


def _notify_session_revoked(user_id) -> None:
    # Corta los WebSockets abiertos del usuario. Nunca lanza.
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"user.{user_id}", {"type": "session.revoked"}
        )
    except Exception:
        logger.warning("SESSION_REVOKE_WS_NOTIFY_FAILED user_id=%s", user_id)
