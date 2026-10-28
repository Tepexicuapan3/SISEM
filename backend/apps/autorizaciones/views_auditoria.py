"""API de auditoria de solicitudes de autorizacion (solo lectura).

Permisos (atomicos, prefijo admin:autorizaciones-auditoria):
  GET listado y linea de tiempo -> read
  GET ?export=xlsx              -> export (y queda en la bitacora de accesos)
"""
from datetime import date

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.services.bitacora_acceso_service import registrar_exportacion
from apps.catalogos.permissions import HasCatalogPermission
from apps.catalogos.views import ErrorMixin, PaginationMixin, _PaginationError

from .auditoria_export import libro_auditoria
from .models import Solicitud, TipoAutorizacion
from .uses_case.auditoria_use_case import MAXIMO_EXPORTACION, AuditoriaUseCase as UseCase

PERMISO_BASE = "admin:autorizaciones-auditoria"
RECURSO_BITACORA = "auditoria_autorizaciones"


def _es_exportacion(request):
    return request.query_params.get("export") == "xlsx"


class _BaseView(ErrorMixin, APIView):
    def get_permissions(self):
        request = getattr(self, "request", None)
        metodo = getattr(request, "method", "GET")
        if metodo not in ("GET", "HEAD", "OPTIONS"):
            accion = "__no_permitido__"
        else:
            accion = "export" if request is not None and _es_exportacion(request) else "read"
        return [HasCatalogPermission(action=accion, catalog=PERMISO_BASE)]


class AuditoriaSolicitudesView(PaginationMixin, _BaseView):
    def _filtros(self, request):
        """(filtros, error). Valida cada parametro antes de consultar."""
        q = request.query_params
        filtros, errores = {}, {}
        for nombre in ("fechaDesde", "fechaHasta"):
            if q.get(nombre):
                try:
                    filtros[nombre] = date.fromisoformat(q[nombre])
                except ValueError:
                    errores[nombre] = ["Formato AAAA-MM-DD"]
        for nombre in ("centroId", "autorizadorId"):
            if q.get(nombre):
                if q[nombre].isdigit():
                    filtros[nombre] = int(q[nombre])
                else:
                    errores[nombre] = ["Debe ser un entero"]
        for nombre, opciones in (("estatus", Solicitud.Estatus.values), ("tipo", TipoAutorizacion.Clave.values)):
            if q.get(nombre):
                if q[nombre] in opciones:
                    filtros[nombre] = q[nombre]
                else:
                    errores[nombre] = [f"Permitidos: {', '.join(opciones)}"]
        if errores:
            return None, self._error(
                request, code="VALIDATION_ERROR", message="Parámetros inválidos",
                http_status=status.HTTP_400_BAD_REQUEST, details=errores,
            )
        return filtros, None

    def get(self, request):
        filtros, error = self._filtros(request)
        if error:
            return error

        if _es_exportacion(request):
            filas = UseCase.listar(filtros, limite=MAXIMO_EXPORTACION)
            registrar_exportacion(request, request.user, recurso=RECURSO_BITACORA)
            respuesta = HttpResponse(
                libro_auditoria(filas),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            respuesta["Content-Disposition"] = 'attachment; filename="auditoria_autorizaciones.xlsx"'
            return respuesta

        try:
            pagina, tamano = self._parse_pagination(request)
        except _PaginationError as exc:
            return exc.response
        elementos, total, paginas = self._paginate_queryset(UseCase.consulta(filtros), pagina, tamano)
        return self._paginated_response(UseCase.filas(elementos), pagina, tamano, total, paginas)


class AuditoriaSolicitudDetalleView(_BaseView):
    def get(self, request, uuid_publico):
        linea = UseCase.linea_de_tiempo(uuid_publico)
        if linea is None:
            return self._error(
                request, code="REQUEST_NOT_FOUND", message="Solicitud no encontrada",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response(linea)
