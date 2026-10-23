from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.administracion.models import BitacoraAcceso, BitacoraSyncExpediente
from apps.administracion.services import bitacora_acceso_service, sync_audit_service
from apps.administracion.views.rbac_views import _authorize, _request_id
from apps.authentication.services.response_service import error_response

from ..use_cases.expedientes.buscar_expediente import (
    ExpedientesNoDisponible,
    buscar_expediente,
    buscar_por_nombre,
)
from ..use_cases.expedientes.actualizar_expediente import actualizar_expediente

# Consultar expedientes (ver, buscar por nombre). Ver frontend
# nav-config.ts y navigation_seed.py: "administracion.panel.expedientes".
PERMISO_EXPEDIENTES = "admin:gestion:expedientes:read"
# Disparar la sincronizacion con SERMED: escribe en la replica y en los
# pacientes de SIRES, por eso es un permiso aparte (change
# auditoria-sync-expedientes, migracion administracion 0015).
PERMISO_ACTUALIZAR_EXPEDIENTES = "admin:gestion:expedientes:update"

# BITACORA_ACCESO.recurso de esta pantalla administrativa (datos personales
# del trabajador y sus derechohabientes, no la historia clinica).
RECURSO_EXPEDIENTE = "expediente_sermed"
RECURSO_BUSQUEDA = "expediente_sermed_busqueda"

Resultado = BitacoraSyncExpediente.Resultado

MENSAJE_NO_DISPONIBLE = (
    "No se pudo consultar SERMED en este momento. No significa que el expediente "
    "no exista: avisá a sistemas."
)


def _expedientes_no_disponibles(request):
    """La replica fallo: distinto de "no encontrado" (incidente 2026-10-23)."""
    return error_response(
        "EXPEDIENTES_NO_DISPONIBLE",
        MENSAJE_NO_DISPONIBLE,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        request_id=_request_id(request),
    )


class ExpedienteView(APIView):
    """GET /api/expedientes/?id_empleado=<no>"""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, auth_error = _authorize(request, PERMISO_EXPEDIENTES)
        if auth_error:
            return auth_error

        id_empleado = request.query_params.get("id_empleado", "").strip()

        if not id_empleado:
            return Response(
                {"error": "Se requiere el parámetro id_empleado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = buscar_expediente(id_empleado)
        except ExpedientesNoDisponible:
            return _expedientes_no_disponibles(request)

        if not resultado["empleados"]:
            return Response(
                {"error": f"No se encontró el expediente {id_empleado}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        bitacora_acceso_service.registrar(
            request, user, accion=BitacoraAcceso.Accion.VER,
            recurso=RECURSO_EXPEDIENTE, no_exp=id_empleado,
        )
        resultado["ultima_actualizacion"] = sync_audit_service.ultima_actualizacion(id_empleado)
        return Response(resultado, status=status.HTTP_200_OK)


class ActualizarExpedienteView(APIView):
    """POST /api/administracion/expedientes/actualizar/"""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user, auth_error = _authorize(request, PERMISO_ACTUALIZAR_EXPEDIENTES, require_csrf=True)
        if auth_error:
            return auth_error

        expediente = str(request.data.get("expediente", "")).strip()

        if not expediente:
            return Response(
                {"error": "Se requiere el campo expediente en el body."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(expediente) > 20:
            return Response(
                {"error": "El expediente no puede tener más de 20 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resultado = actualizar_expediente(
            expediente,
            usuario=user,
            origen=BitacoraSyncExpediente.Origen.BOTON,
            request=request,
        )

        estado = resultado["estado"]
        if estado == Resultado.OCUPADO:
            return error_response(
                "SYNC_EN_CURSO",
                resultado["errores"][0],
                status.HTTP_409_CONFLICT,
                details={"id_sync": resultado["id_sync"]},
                request_id=_request_id(request),
            )
        if estado == Resultado.ERROR:
            return error_response(
                "SYNC_ERROR",
                "No se pudo actualizar el expediente desde SERMED; no se aplicó ningún cambio.",
                status.HTTP_502_BAD_GATEWAY,
                details={"id_sync": resultado["id_sync"], "errores": resultado["errores"]},
                request_id=_request_id(request),
            )
        # OK o PARCIAL: la replica quedo al dia; PARCIAL trae sus errores.
        return Response(resultado, status=status.HTTP_200_OK)


class BuscarPorNombreView(APIView):
    """GET /api/administracion/expedientes/buscar-nombre/?nombre=<texto>"""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, auth_error = _authorize(request, PERMISO_EXPEDIENTES)
        if auth_error:
            return auth_error

        nombre = request.query_params.get("nombre", "").strip()

        if len(nombre) < 3:
            return Response(
                {"error": "El parámetro nombre debe tener al menos 3 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultados = buscar_por_nombre(nombre)
        except ExpedientesNoDisponible:
            return _expedientes_no_disponibles(request)
        bitacora_acceso_service.registrar(
            request, user, accion=BitacoraAcceso.Accion.VER, recurso=RECURSO_BUSQUEDA,
        )
        return Response(resultados, status=status.HTTP_200_OK)
