"""API de cancelacion de nota cerrada (change cancelacion-nota-cascada).

  GET  visits/<id>/consultation/cancellation-preview
  POST visits/<id>/consultation/cancel
  GET  visits/<id>/consultation/cancellation

Errores de re-autenticacion: 403 REAUTH_FAILED / 423 REAUTH_LOCKED (nunca 401:
el interceptor del frontend hace refresh/logout en 401).
"""
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.audit_service import log_event
from apps.authentication.services.response_service import error_response, get_request_id
from apps.recepcion.services.errors import VisitDomainError

from .uses_case.note_cancellation_usecase import (
    cancel_consultation,
    get_cancellation,
    get_cancellation_preview,
)
from .views import (
    _actor_context,
    _auth_or_error,
    _csrf_or_error,
    _domain_error_response,
)


_REAUTH_ERROR_CODES = frozenset({"REAUTH_FAILED", "REAUTH_LOCKED"})


def _log_reauth_failure(request, user, actor_id, visit_id, exc):
    """R2.6 SHOULD: registra el intento fallido de re-autenticacion.

    Corre FUERA del atomic de la cascada (la re-auth falla antes de abrirlo),
    asi que no revierte ni afecta nada. Nunca incluye la contrasena: solo
    codigo de error y visita. Es best-effort (raise_on_error=False).
    """
    log_event(
        request,
        "ConsultationNoteCancelReauthFailed",
        "FAILURE",
        actor_user=user,
        error_code=exc.code,
        resource_type="consulta_medica",
        resource_id=visit_id,
        meta={
            "module": "consulta_medica",
            "endpoint": request.path,
            "actorId": actor_id,
            "visitId": visit_id,
        },
    )


class CancelConsultationSerializer(serializers.Serializer):
    motivoId = serializers.IntegerField(min_value=1)
    motivoDetalle = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=500,
    )
    # trim_whitespace=False: la contrasena se compara tal cual.
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class VisitNoteCancellationPreviewView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        _, _, permissions = _actor_context(user)
        try:
            payload = get_cancellation_preview(visit_id, user, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)


class VisitNoteCancellationDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        _, _, permissions = _actor_context(user)
        try:
            payload = get_cancellation(visit_id, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitNoteCancelView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CancelConsultationSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, _, permissions = _actor_context(user)
        data = serializer.validated_data

        def audit_hook(*, resource_id, datos_antes, datos_despues, meta=None, strict=True):
            log_event(
                request,
                "ConsultationNoteCancelled",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "actorId": actor_id,
                    **(meta or {}),
                },
                raise_on_error=strict,
            )

        try:
            payload = cancel_consultation(
                visit_id,
                user,
                permissions,
                motivo_id=data["motivoId"],
                motivo_detalle=(data.get("motivoDetalle") or None),
                password=data["password"],
                audit_hook=audit_hook,
                request_id=get_request_id(request),
            )
        except VisitDomainError as exc:
            if exc.code in _REAUTH_ERROR_CODES:
                _log_reauth_failure(request, user, actor_id, visit_id, exc)
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)
