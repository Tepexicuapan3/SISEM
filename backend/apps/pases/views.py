import logging

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils import timezone
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

from .models import Referral
from .serializers import CancelReferralSerializer, CreateReferralSerializer
from .services.report_export_service import build_referral_report_workbook
from .uses_case.referral_usecase import (
    cancel_referral,
    create_referral,
    get_patient_referrals,
    get_referral_report,
)

logger = logging.getLogger(__name__)


def _auth_or_error(request):
    try:
        return authenticate_request(request), None
    except AuthServiceError as exc:
        return None, error_response(
            exc.code,
            exc.message,
            exc.status_code,
            details=exc.details,
            request_id=get_request_id(request),
        )


def _csrf_or_error(request):
    if validate_csrf(request):
        return None
    return error_response(
        "PERMISSION_DENIED",
        "No tienes permiso para esta accion",
        status.HTTP_403_FORBIDDEN,
        request_id=get_request_id(request),
    )


def _domain_error_response(request, exc):
    return error_response(
        exc.code,
        exc.message,
        exc.status_code,
        details=exc.details,
        request_id=get_request_id(request),
    )


def _actor_context(user):
    auth_user = UserRepository.build_auth_user(user)
    return (
        user.id_usuario,
        auth_user.get("roles", []),
        auth_user.get("permissions", []),
    )


def _parse_pk_num(request):
    raw_value = request.query_params.get("pkNum", "0")
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


@method_decorator(csrf_exempt, name="dispatch")
class VisitReferralCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CreateReferralSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)
        data = serializer.validated_data

        try:
            payload = create_referral(
                visit_id,
                roles,
                referral_type=data["referralType"],
                destination_center_id=data.get("destinationCenterId"),
                specialty_id=data.get("specialtyId"),
                requested_care=data.get("requestedCare"),
                visit_type=data.get("visitType"),
                studies=data.get("studies"),
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "ReferralCreated",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "pases",
                "endpoint": request.path,
                "visitId": visit_id,
                "referralType": data["referralType"],
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class ReferralCancelView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, referral_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CancelReferralSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        try:
            payload = cancel_referral(
                referral_id,
                roles,
                cancellation_reason_id=serializer.validated_data["cancellationReasonId"],
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "ReferralCancelled",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "pases",
                "endpoint": request.path,
                "referralId": referral_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientReferralsHistoryView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error

        pk_num = _parse_pk_num(request)
        if pk_num is None:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"pkNum": ["pkNum debe ser un numero entero."]},
                request_id=get_request_id(request),
            )

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_patient_referrals(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ReferralReportView(APIView):
    """
    Informe de pases emitidos en un rango de fechas (default: hoy).
    Equivalente moderno de body-repases.jsp/body-repingresados.jsp/
    body-rephospital.jsp del legado -- ver
    docs/architecture/legacy-reports-inventory.md.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        today = timezone.localdate()
        raw_start = request.query_params.get("fechaInicio")
        raw_end = request.query_params.get("fechaFin")

        fecha_inicio = parse_date(raw_start) if raw_start else today
        fecha_fin = parse_date(raw_end) if raw_end else today

        if (raw_start and fecha_inicio is None) or (raw_end and fecha_fin is None):
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"fecha": ["Formato esperado: YYYY-MM-DD."]},
                request_id=get_request_id(request),
            )

        referral_type = request.query_params.get("tipoPase") or None
        if referral_type and referral_type not in Referral.ReferralType.values:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"tipoPase": [f"Debe ser uno de: {', '.join(Referral.ReferralType.values)}"]},
                request_id=get_request_id(request),
            )

        referral_status = request.query_params.get("status") or None
        if referral_status and referral_status not in Referral.Status.values:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"status": [f"Debe ser uno de: {', '.join(Referral.Status.values)}"]},
                request_id=get_request_id(request),
            )

        no_exp = request.query_params.get("noExp") or None

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_referral_report(
                fecha_inicio,
                fecha_fin,
                roles,
                permissions,
                referral_type=referral_type,
                status=referral_status,
                no_exp=no_exp,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        if request.query_params.get("export") == "xlsx":
            content = build_referral_report_workbook(payload["items"])
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            filename = f"informe_pases_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.xlsx"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return Response(payload, status=status.HTTP_200_OK)
