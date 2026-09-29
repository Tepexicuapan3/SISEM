"""
`GET bitacora-acceso` -- consulta de la bitacora de acceso al expediente
clinico para calidad/auditoria (change `bitacora-acceso-expediente`, Fase 3
del plan NOM-024). Solo lectura, gateada por `admin:auditoria:accesos:read`.
"""
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.models import BitacoraAcceso
from apps.administracion.repositories.access_log_repository import (
    EVENT_TYPES,
    AccessLogRepository,
)
from apps.authentication.services.response_service import error_response, get_request_id

from .rbac_read_views import _parse_pagination
from .rbac_views import _authorize

ACCESS_LOG_READ_PERMISSION = "admin:auditoria:accesos:read"


class AccessLogListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, error = _authorize(request, ACCESS_LOG_READ_PERMISSION)
        if error:
            return error

        page, page_size, pagination_error = _parse_pagination(request)
        if pagination_error:
            return pagination_error

        params = request.query_params
        errors = {}

        event_type = params.get("tipo") or None
        if event_type and event_type not in EVENT_TYPES:
            errors["tipo"] = [f"Debe ser uno de: {', '.join(EVENT_TYPES)}."]
        action = params.get("accion") or None
        if action and action not in BitacoraAcceso.Accion.values:
            errors["accion"] = [f"Debe ser uno de: {', '.join(BitacoraAcceso.Accion.values)}."]

        fecha_inicio = _parse_optional_date(params.get("fechaInicio"), "fechaInicio", errors)
        fecha_fin = _parse_optional_date(params.get("fechaFin"), "fechaFin", errors)
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            errors["fechaFin"] = ["Debe ser igual o posterior a fechaInicio."]

        pk_num = None
        raw_pk_num = params.get("pkNum")
        if raw_pk_num not in (None, ""):
            try:
                pk_num = int(raw_pk_num)
            except ValueError:
                errors["pkNum"] = ["pkNum debe ser un numero entero."]

        if errors:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en los filtros",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=errors,
                request_id=get_request_id(request),
            )

        payload = AccessLogRepository.list_events(
            page=page,
            page_size=page_size,
            event_type=event_type,
            action=action,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            no_exp=(params.get("noExp") or "").strip() or None,
            pk_num=pk_num,
            section=params.get("seccion") or None,
            actor_username=(params.get("usuario") or "").strip() or None,
        )
        return Response(payload, status=status.HTTP_200_OK)


def _parse_optional_date(raw_value, field_name, errors):
    if not raw_value:
        return None
    # parse_date devuelve None si el formato no calza, pero LANZA ValueError
    # si el formato calza con una fecha imposible (ej. mes 13).
    try:
        parsed = parse_date(raw_value)
    except ValueError:
        parsed = None
    if parsed is None:
        errors[field_name] = ["Fecha invalida, formato esperado AAAA-MM-DD."]
    return parsed
