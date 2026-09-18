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

from .models import AmbulanceRequest
from .serializers import (
    AuthorizeAmbulanceRequestSerializer,
    CreateAmbulanceRequestSerializer,
    RejectAmbulanceRequestSerializer,
)
from .services.report_export_service import build_ambulance_report_workbook
from .uses_case.ambulance_request_usecase import (
    authorize_request,
    cancel_request,
    create_request,
    get_request_report,
    list_requests,
    reject_request,
)


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


def _actor_context(user):
    auth_user = UserRepository.build_auth_user(user)
    return user.id_usuario, auth_user.get("permissions", [])


@method_decorator(csrf_exempt, name="dispatch")
class AmbulanceRequestsListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, permissions = _actor_context(user)
        filters = {
            "authorization_status": request.query_params.get("authorizationStatus") or None,
            "status": request.query_params.get("status") or None,
            "no_exp": request.query_params.get("noExp") or None,
        }
        fecha_inicio = parse_date(request.query_params.get("fechaInicio") or "")
        fecha_fin = parse_date(request.query_params.get("fechaFin") or "")
        if fecha_inicio:
            filters["fecha_inicio"] = fecha_inicio
        if fecha_fin:
            filters["fecha_fin"] = fecha_fin

        try:
            payload = list_requests(permissions=permissions, **filters)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CreateAmbulanceRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY, details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, permissions = _actor_context(user)
        data = serializer.validated_data

        try:
            payload = create_request(
                no_exp=data["noExp"],
                pk_num=data.get("pkNum", 0),
                requesting_clinic_id=data["requestingClinicId"],
                requested_by_name=data["requestedByName"],
                requested_by_relationship_id=data.get("requestedByRelationshipId"),
                social_work_notes=data.get("socialWorkNotes"),
                reason_id=data["reasonId"],
                reason_notes=data.get("reasonNotes"),
                diagnosis_text=data.get("diagnosisText"),
                origin_street=data.get("originStreet"),
                origin_zip=data.get("originZip"),
                origin_neighborhood=data.get("originNeighborhood"),
                origin_borough=data.get("originBorough"),
                origin_phone=data.get("originPhone"),
                origin_reference=data.get("originReference"),
                destination_id=data["destinationId"],
                schedules=data["schedules"],
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "AmbulanceRequestCreated",
            "SUCCESS",
            actor_user=user,
            resource_type="ambulancias",
            resource_id=payload["id"],
            datos_antes=None,
            datos_despues={
                "status": payload["status"],
                "authorizationStatus": payload["authorizationStatus"],
                "reasonId": payload["reasonId"],
                "destinationId": payload["destinationId"],
                "requestingClinicId": payload["requestingClinicId"],
                "schedulesCount": len(payload["schedules"]),
            },
            meta={
                "module": "ambulancias", "endpoint": request.path,
                "actorId": actor_id, "folio": payload["folio"],
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class AmbulanceRequestAuthorizeView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, request_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = AuthorizeAmbulanceRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY, details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, permissions = _actor_context(user)

        def audit_hook(*, resource_id, folio, datos_antes, datos_despues):
            log_event(
                request,
                "AmbulanceRequestAuthorized",
                "SUCCESS",
                actor_user=user,
                resource_type="ambulancias",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "ambulancias", "endpoint": request.path,
                    "actorId": actor_id, "folio": folio,
                },
                raise_on_error=True,
            )

        try:
            payload = authorize_request(
                request_id,
                service_number=serializer.validated_data["serviceNumber"],
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class AmbulanceRequestRejectView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, request_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = RejectAmbulanceRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY, details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, permissions = _actor_context(user)

        def audit_hook(*, resource_id, folio, datos_antes, datos_despues):
            log_event(
                request,
                "AmbulanceRequestRejected",
                "SUCCESS",
                actor_user=user,
                resource_type="ambulancias",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "ambulancias", "endpoint": request.path,
                    "actorId": actor_id, "folio": folio,
                },
                raise_on_error=True,
            )

        try:
            payload = reject_request(
                request_id,
                notes=serializer.validated_data["notes"],
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class AmbulanceRequestCancelView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, request_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        actor_id, permissions = _actor_context(user)

        def audit_hook(*, resource_id, folio, datos_antes, datos_despues):
            log_event(
                request,
                "AmbulanceRequestCancelled",
                "SUCCESS",
                actor_user=user,
                resource_type="ambulancias",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "ambulancias", "endpoint": request.path,
                    "actorId": actor_id, "folio": folio,
                },
                raise_on_error=True,
            )

        try:
            payload = cancel_request(
                request_id, actor_id=actor_id, permissions=permissions, audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class AmbulanceRequestReportView(APIView):
    """Informe de solicitudes de traslado en un rango de fechas (default: hoy)."""

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
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"fecha": ["Formato esperado: YYYY-MM-DD."]},
                request_id=get_request_id(request),
            )

        authorization_status = request.query_params.get("authorizationStatus") or None
        if authorization_status and authorization_status not in AmbulanceRequest.AuthorizationStatus.values:
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={
                    "authorizationStatus": [
                        f"Debe ser uno de: {', '.join(AmbulanceRequest.AuthorizationStatus.values)}"
                    ]
                },
                request_id=get_request_id(request),
            )

        _, permissions = _actor_context(user)

        try:
            payload = get_request_report(
                fecha_inicio, fecha_fin, permissions=permissions,
                authorization_status=authorization_status,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        if request.query_params.get("export") == "xlsx":
            content = build_ambulance_report_workbook(payload["items"])
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            filename = f"informe_ambulancias_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.xlsx"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return Response(payload, status=status.HTTP_200_OK)
