"""
Solicitudes ARCO (change `solicitudes-arco`, Fase 4 del plan NOM-024):
cola de gestion para el area de compliance. Lectura con
`admin:arco:read`, alta y cambio de estatus con `admin:arco:write`.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.models import SolicitudArco
from apps.administracion.serializers.arco_serializers import (
    ChangeSolicitudArcoStatusSerializer,
    CreateSolicitudArcoSerializer,
)
from apps.administracion.use_cases.arco.arco_usecase import (
    ArcoError,
    change_status,
    create_solicitud,
    get_solicitud,
    list_solicitudes,
)
from apps.authentication.services.audit_service import log_event
from apps.authentication.services.response_service import error_response, get_request_id

from .rbac_read_views import _parse_pagination
from .rbac_views import _authorize

ARCO_READ_PERMISSION = "admin:arco:read"
ARCO_WRITE_PERMISSION = "admin:arco:write"


def _validation_error(request, details):
    return error_response(
        "VALIDATION_ERROR",
        "Hay errores en el formulario",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=details,
        request_id=get_request_id(request),
    )


def _arco_error_response(request, exc):
    return error_response(
        exc.code, exc.message, exc.status_code, details=exc.details,
        request_id=get_request_id(request),
    )


def _audit_hook_for(request, user):
    def audit_hook(*, action, resource_id, datos_antes, datos_despues):
        # Estricta: si la auditoria falla, el atomic() del caso de uso
        # revierte el alta/cambio de estatus completo.
        log_event(
            request,
            action,
            "SUCCESS",
            actor_user=user,
            resource_type="solicitud_arco",
            resource_id=resource_id,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            meta={"module": "administracion", "endpoint": request.path},
            raise_on_error=True,
        )

    return audit_hook


class SolicitudesArcoView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, error = _authorize(request, ARCO_READ_PERMISSION)
        if error:
            return error

        page, page_size, pagination_error = _parse_pagination(request)
        if pagination_error:
            return pagination_error

        params = request.query_params
        errors = {}
        estatus = params.get("estatus") or None
        if estatus and estatus not in SolicitudArco.Estatus.values:
            errors["estatus"] = ["Estatus invalido."]
        tipo = params.get("tipo") or None
        if tipo and tipo not in SolicitudArco.Tipo.values:
            errors["tipo"] = ["Tipo invalido."]
        if errors:
            return _validation_error(request, errors)

        payload = list_solicitudes(
            page=page,
            page_size=page_size,
            estatus=estatus,
            tipo=tipo,
            no_exp=(params.get("noExp") or "").strip() or None,
            overdue=params.get("vencidas") in ("1", "true"),
        )
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request):
        user, error = _authorize(request, ARCO_WRITE_PERMISSION, require_csrf=True)
        if error:
            return error

        serializer = CreateSolicitudArcoSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        received = serializer.validated_data.get("receivedDate")
        if received and received > timezone.localdate():
            return _validation_error(
                request, {"receivedDate": ["La fecha de recepcion no puede ser futura."]},
            )

        try:
            payload = create_solicitud(
                serializer.validated_data, actor=user, audit_hook=_audit_hook_for(request, user),
            )
        except ArcoError as exc:
            return _arco_error_response(request, exc)

        return Response(payload, status=status.HTTP_201_CREATED)


class SolicitudArcoDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, solicitud_id):
        _, error = _authorize(request, ARCO_READ_PERMISSION)
        if error:
            return error

        try:
            payload = get_solicitud(solicitud_id)
        except ArcoError as exc:
            return _arco_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


class SolicitudArcoStatusView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, solicitud_id):
        user, error = _authorize(request, ARCO_WRITE_PERMISSION, require_csrf=True)
        if error:
            return error

        serializer = ChangeSolicitudArcoStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        try:
            payload = change_status(
                solicitud_id,
                serializer.validated_data,
                actor=user,
                audit_hook=_audit_hook_for(request, user),
            )
        except ArcoError as exc:
            return _arco_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)
