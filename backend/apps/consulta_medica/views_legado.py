"""
Datos del legado que el medico confirma (diseño del 2026-10-27, paso 3):
GET  patients/<no_exp>/legacy-review?pkNum=  -> secciones pendientes
POST patients/<no_exp>/legacy-review?pkNum=  -> {seccion, aceptar: [ref...]}
Solo medicos (misma regla que el historial del legado).
"""
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.response_service import error_response, get_request_id
from apps.recepcion.services.errors import VisitDomainError

from .services import legado_archivo, legado_confirmacion
from .services.record_access_audit_service import RecordSection, log_patient_record_access
from .uses_case.consultation_usecase import ensure_doctor_role
from .views import _actor_context, _auth_or_error, _csrf_or_error, _domain_error_response, _parse_pk_num


def _pk_num_or_error(request):
    pk_num = _parse_pk_num(request)
    if pk_num is None:
        return None, error_response(
            "VALIDATION_ERROR", "Hay errores en el formulario", status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"pkNum": ["pkNum debe ser un numero entero."]}, request_id=get_request_id(request),
        )
    return pk_num, None


def _no_disponible(exc):
    return Response({"disponible": False, "mensaje": str(exc), "secciones": []}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientLegacyReviewView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return error
        actor_id, roles, permissions = _actor_context(user)
        try:
            ensure_doctor_role(roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        if not legado_archivo.disponible():
            return _no_disponible(legado_archivo.MENSAJE_NO_DISPONIBLE)
        try:
            secciones = legado_confirmacion.propuestas(no_exp, pk_num)
        except legado_archivo.LegadoNoDisponible as exc:
            return _no_disponible(exc)
        log_patient_record_access(
            request, user, actor_id=actor_id, no_exp=no_exp, pk_num=pk_num,
            section=RecordSection.LEGACY_CONSULTATIONS,
        )
        return Response({"disponible": True, "secciones": secciones}, status=status.HTTP_200_OK)

    def post(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return error
        seccion = request.data.get("seccion")
        aceptar = request.data.get("aceptar")
        if not isinstance(aceptar, list) or not all(isinstance(ref, str) for ref in aceptar):
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario", status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"aceptar": ["Lista de referencias del legado."]}, request_id=get_request_id(request),
            )
        actor_id, roles, permissions = _actor_context(user)
        try:
            ensure_doctor_role(roles, permissions)
            resultado = legado_confirmacion.confirmar(no_exp, pk_num, seccion, aceptar, user_id=actor_id)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        except legado_archivo.LegadoNoDisponible as exc:
            return error_response("LEGADO_NO_DISPONIBLE", str(exc), status.HTTP_503_SERVICE_UNAVAILABLE,
                                  request_id=get_request_id(request))
        return Response(resultado, status=status.HTTP_200_OK)
