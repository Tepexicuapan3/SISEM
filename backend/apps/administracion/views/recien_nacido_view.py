"""
Plan identidad del paciente, bloque C1: recien nacidos provisionales desde
Administracion -> Expedientes (decision del usuario, 2026-10-23).

GET  /api/v1/expedientes/<no_exp>/recien-nacidos/            lista + candidatos (lectura)
POST /api/v1/expedientes/<no_exp>/recien-nacidos/            alta (recien_nacidos)
POST /api/v1/expedientes/recien-nacidos/<id>/vincular/       "es el mismo" (vincular)
POST /api/v1/expedientes/recien-nacidos/<id>/descartar/      "no es" (vincular)
POST /api/v1/expedientes/recien-nacidos/<id>/extender-vigencia/  hoy + 60 (recien_nacidos)
"""
from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.views.rbac_views import _authorize, _request_id
from apps.authentication.services.response_service import error_response
from apps.consulta_medica.services import newborn_service
from apps.recepcion.services.errors import VisitDomainError

PERMISO_LEER = "admin:gestion:expedientes:read"
PERMISO_REGISTRAR = "admin:gestion:expedientes:recien_nacidos"
PERMISO_VINCULAR = "admin:gestion:expedientes:vincular"


def _error(request, exc: VisitDomainError):
    return error_response(exc.code, exc.message, exc.status_code, details=exc.details or None,
                          request_id=_request_id(request))


def _validacion(request, campo, mensaje):
    return error_response("VALIDATION_ERROR", "Hay errores en el formulario.", status.HTTP_422_UNPROCESSABLE_ENTITY,
                          details={campo: [mensaje]}, request_id=_request_id(request))


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


class RecienNacidosView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, no_exp):
        _, auth_error = _authorize(request, PERMISO_LEER)
        if auth_error:
            return auth_error
        return Response(newborn_service.listar(no_exp), status=status.HTTP_200_OK)

    def post(self, request, no_exp):
        user, auth_error = _authorize(request, PERMISO_REGISTRAR, require_csrf=True)
        if auth_error:
            return auth_error
        datos = request.data
        try:
            fecha = date.fromisoformat(str(datos.get("birthDate", "")))
        except ValueError:
            return _validacion(request, "birthDate", "Fecha de nacimiento inválida (AAAA-MM-DD).")
        orden = _entero(datos.get("birthOrder", 1))
        if orden is None:
            return _validacion(request, "birthOrder", "El orden de nacimiento debe ser un número.")
        try:
            resultado = newborn_service.registrar_recien_nacido(
                no_exp,
                paterno=datos.get("paternalSurname"), materno=datos.get("maternalSurname"),
                nombre=datos.get("firstName"), fecha_nacimiento=fecha, sexo=datos.get("sex"),
                madre=datos.get("motherName"), orden=orden, curp=datos.get("curp"), user=user,
                confirmar_aunque_exista=bool(datos.get("confirmarAunqueExista", False)),
            )
        except VisitDomainError as exc:
            return _error(request, exc)
        return Response(resultado, status=status.HTTP_201_CREATED)


class _AccionSobreProvisional(APIView):
    authentication_classes = []
    permission_classes = []

    def _ejecutar(self, request, id_paciente, accion):
        user, auth_error = _authorize(request, PERMISO_VINCULAR, require_csrf=True)
        if auth_error:
            return auth_error
        pk_num = _entero(request.data.get("pkNum"))
        if pk_num is None or pk_num <= 0:
            return _validacion(request, "pkNum", "Indicá el familiar de SERMED (pkNum).")
        try:
            resultado = accion(id_paciente, pk_num, user)
        except VisitDomainError as exc:
            return _error(request, exc)
        return Response(resultado, status=status.HTTP_200_OK)


class VincularRecienNacidoView(_AccionSobreProvisional):
    def post(self, request, id_paciente):
        return self._ejecutar(
            request, id_paciente, lambda pk, pk_num, user: newborn_service.vincular(pk, pk_num, user=user),
        )


class DescartarCoincidenciaView(_AccionSobreProvisional):
    def post(self, request, id_paciente):
        motivo = request.data.get("motivo")
        return self._ejecutar(
            request, id_paciente,
            lambda pk, pk_num, user: newborn_service.descartar(pk, pk_num, motivo=motivo, user=user),
        )


class ExtenderVigenciaRecienNacidoView(APIView):
    """Mismo permiso que el alta: en el legado la misma pantalla registra y renueva."""
    authentication_classes = []
    permission_classes = []

    def post(self, request, id_paciente):
        user, auth_error = _authorize(request, PERMISO_REGISTRAR, require_csrf=True)
        if auth_error:
            return auth_error
        try:
            resultado = newborn_service.extender_vigencia(
                id_paciente, motivo=request.data.get("motivo"), user=user,
            )
        except VisitDomainError as exc:
            return _error(request, exc)
        return Response(resultado, status=status.HTTP_200_OK)
