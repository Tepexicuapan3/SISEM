from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.views.rbac_views import _audit, _authorize, _request_id
from apps.authentication.models import SyUsuario
from apps.authentication.services.errors import PolicyStoreUnavailableError
from apps.authentication.services.login_unlock import unlock_login
from apps.authentication.services.response_service import error_response
from apps.authentication.services.session_revocation import revoke_user_sessions

PERMISSION = "admin:gestion:usuarios:credenciales"


def _fail(request, action, user_id, code, message, http_status, target_user=None):
    # Registra el FAIL en auditoria y arma la respuesta de error.
    _audit(
        request,
        action,
        "user",
        resource_id=user_id,
        result="FAIL",
        error_code=code,
        target_user=target_user,
    )
    return error_response(
        code, message, http_status, request_id=_request_id(request)
    )


class UserForceLogoutView(APIView):
    # Cierra la sesion activa de otro usuario (libera el 409 de sesion unica).
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, user_id):
        action = "RBAC_USER_FORCE_LOGOUT"
        actor, auth_error = _authorize(request, PERMISSION, require_csrf=True)
        if auth_error:
            _audit(
                request,
                action,
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        user = SyUsuario.objects.filter(id_usuario=user_id).first()
        if not user:
            return _fail(
                request, action, user_id,
                "USER_NOT_FOUND", "Usuario no encontrado",
                status.HTTP_404_NOT_FOUND,
            )

        if actor.id_usuario == user.id_usuario:
            return _fail(
                request, action, user.id_usuario,
                "SELF_FORCE_LOGOUT_NOT_ALLOWED",
                "No puedes forzar el cierre de tu propia sesión",
                status.HTTP_409_CONFLICT, target_user=user,
            )

        # Aqui la accion ES Redis: si no se pudo limpiar, no se reporta exito.
        if not revoke_user_sessions(user):
            return _fail(
                request, action, user.id_usuario,
                "SERVICE_UNAVAILABLE", "Servicio temporalmente no disponible",
                status.HTTP_503_SERVICE_UNAVAILABLE, target_user=user,
            )

        payload = {"id": user.id_usuario, "sessionRevoked": True}
        _audit(
            request,
            action,
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            after=payload,
            target_user=user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class UserUnlockView(APIView):
    # Quita el bloqueo temporal de login (intentos fallidos) de una cuenta.
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, user_id):
        action = "RBAC_USER_UNLOCK"
        actor, auth_error = _authorize(request, PERMISSION, require_csrf=True)
        if auth_error:
            _audit(
                request,
                action,
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        user = SyUsuario.objects.filter(id_usuario=user_id).first()
        if not user:
            return _fail(
                request, action, user_id,
                "USER_NOT_FOUND", "Usuario no encontrado",
                status.HTTP_404_NOT_FOUND,
            )

        try:
            unlock_login(user)
        except PolicyStoreUnavailableError:
            return _fail(
                request, action, user.id_usuario,
                "SERVICE_UNAVAILABLE", "Servicio temporalmente no disponible",
                status.HTTP_503_SERVICE_UNAVAILABLE, target_user=user,
            )

        payload = {"id": user.id_usuario, "unlocked": True}
        _audit(
            request,
            action,
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            after=payload,
            target_user=user,
        )
        return Response(payload, status=status.HTTP_200_OK)
