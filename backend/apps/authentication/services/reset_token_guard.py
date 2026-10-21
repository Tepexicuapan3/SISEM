from rest_framework_simplejwt.settings import api_settings

from apps.authentication.infrastructure.reset_token_store import ResetTokenStore
from apps.authentication.services.errors import (
    AuthServiceError,
    PolicyStoreUnavailableError,
)
from apps.authentication.services.token_service import RESET_MAX_AGE

reset_token_store = ResetTokenStore()


def consume_reset_jti(payload) -> None:
    # Reset token de un solo uso. Fail-closed si Redis no responde.
    jti = payload.get(api_settings.JTI_CLAIM)
    if not jti:
        raise AuthServiceError("TOKEN_INVALID", "Token inválido", 401)

    try:
        first_use = reset_token_store.mark_consumed(jti, RESET_MAX_AGE)
    except PolicyStoreUnavailableError as exc:
        raise AuthServiceError(
            "SERVICE_UNAVAILABLE",
            "Servicio temporalmente no disponible",
            503,
        ) from exc

    if not first_use:
        raise AuthServiceError("TOKEN_INVALID", "Token inválido", 401)


def ensure_user_can_reset(user) -> None:
    # Mismo error para cualquier estado: no revela si la cuenta existe/esta baja.
    if not user.est_activo or user.fch_baja or user.est_bloqueado:
        raise AuthServiceError("TOKEN_INVALID", "Token inválido", 401)
