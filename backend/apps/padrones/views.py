"""
API de padrones clinicos (P-04). Mismo esqueleto que ambulancias:
autenticacion por sesion, CSRF en escrituras, errores de dominio con
error_response y evento de auditoria por cada inscripcion o baja.

  GET  padrones/<registry>              lista (filtros noExp, pkNum, centerId, status)
  POST padrones/<registry>              inscribir
  POST padrones/<registry>/<id>/baja    dar de baja la inscripcion
  GET  padrones/<registry>/opciones     CIE-10 o discapacidades para inscribir (?search=)
<registry> = cronicos | discapacidad
"""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.audit_service import log_event
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.recepcion.services.errors import VisitDomainError

from .serializers import DischargeSerializer, EnrollSerializer
from .uses_case import padron_usecase as uc


def _auth_or_error(request):
    try:
        return authenticate_request(request), None
    except AuthServiceError as exc:
        return None, error_response(
            exc.code, exc.message, exc.status_code, details=exc.details,
            request_id=get_request_id(request),
        )


def _csrf_or_error(request):
    if validate_csrf(request):
        return None
    return error_response(
        "PERMISSION_DENIED", "No tienes permiso para esta accion",
        status.HTTP_403_FORBIDDEN, request_id=get_request_id(request),
    )


def _domain_error_response(request, exc):
    return error_response(
        exc.code, exc.message, exc.status_code, details=exc.details,
        request_id=get_request_id(request),
    )


def _validation_response(request, serializer):
    return error_response(
        "VALIDATION_ERROR", "Hay errores en el formulario",
        status.HTTP_422_UNPROCESSABLE_ENTITY, details=serializer.errors,
        request_id=get_request_id(request),
    )


def _access(user):
    auth_user = UserRepository.build_auth_user(user)
    return auth_user.get("permissions", []), auth_user.get("roles", [])


def _audit(request, user, action, registry, enrollment, before, after):
    log_event(
        request, action, "SUCCESS", actor_user=user,
        resource_type=f"padron_{registry}", resource_id=enrollment.id,
        datos_antes=before, datos_despues=after,
        meta={"module": "padrones", "registry": registry, "noExp": enrollment.no_exp},
    )


def _parse_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


@method_decorator(csrf_exempt, name="dispatch")
class RegistryListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, registry):
        user, error = _auth_or_error(request)
        if error:
            return error
        permissions, roles = _access(user)
        params = request.query_params
        try:
            payload = uc.list_enrollments(
                registry, permissions=permissions, roles=roles,
                no_exp=(params.get("noExp") or "").strip() or None,
                pk_num=_parse_int(params.get("pkNum")),
                center_id=_parse_int(params.get("centerId")),
                status=params.get("status") or None,
                page=_parse_int(params.get("page")) or 1,
                page_size=_parse_int(params.get("pageSize")) or 20,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, registry):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error
        serializer = EnrollSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_response(request, serializer)
        data = serializer.validated_data
        permissions, roles = _access(user)
        try:
            enrollment = uc.enroll(
                registry, no_exp=data["noExp"], pk_num=data.get("pkNum", 0),
                item_id=data["itemId"].strip(), center_id=data.get("centerId"),
                enrolled_on=data.get("enrolledOn"), notes=data.get("notes"),
                actor=user, permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        spec = uc.get_kind(registry)
        payload = uc.to_contract(spec, enrollment, permissions=permissions, roles=roles)
        _audit(request, user, "RegistryEnrollmentCreated", registry, enrollment, None, {
            "itemId": str(getattr(enrollment, f"{spec.item_field}_id")),
            "centerId": enrollment.center_id, "enrolledOn": str(enrollment.enrolled_on),
        })
        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class RegistryOptionsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, registry):
        user, error = _auth_or_error(request)
        if error:
            return error
        permissions, roles = _access(user)
        try:
            payload = uc.search_options(
                registry, search=request.query_params.get("search"), permissions=permissions, roles=roles,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload)


@method_decorator(csrf_exempt, name="dispatch")
class RegistryDischargeView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, registry, enrollment_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error
        serializer = DischargeSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_response(request, serializer)
        data = serializer.validated_data
        permissions, roles = _access(user)
        try:
            enrollment = uc.discharge(
                registry, enrollment_id, reason_id=data["reasonId"], detail=data.get("detail"),
                discharged_on=data.get("dischargedOn"), actor=user, permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        spec = uc.get_kind(registry)
        _audit(request, user, "RegistryEnrollmentDischarged", registry, enrollment,
               {"status": "activo"},
               {"status": enrollment.status, "reasonId": enrollment.discharge_reason_id,
                "dischargedOn": str(enrollment.discharged_on)})
        return Response(uc.to_contract(spec, enrollment, permissions=permissions, roles=roles))
