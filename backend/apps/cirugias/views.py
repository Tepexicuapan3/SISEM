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

from .models import SurgerySchedule
from .serializers import CancelSurgerySerializer, ScheduleSurgerySerializer
from .services.report_export_service import build_surgery_report_workbook
from .uses_case.surgery_usecase import (
    cancel_surgery,
    get_surgery_report,
    list_surgeries,
    schedule_surgery,
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
class SurgeriesListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, permissions = _actor_context(user)
        filters = {
            "surgeon_id": request.query_params.get("surgeonId") or None,
            "classification_id": request.query_params.get("classificationId") or None,
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
            payload = list_surgeries(permissions=permissions, **filters)
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

        serializer = ScheduleSurgerySerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY, details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, permissions = _actor_context(user)
        data = serializer.validated_data

        try:
            payload = schedule_surgery(
                no_exp=data["noExp"],
                pk_num=data.get("pkNum", 0),
                surgeon_id=data["surgeonId"],
                surgery_type_id=data["surgeryTypeId"],
                classification_id=data["classificationId"],
                origin_clinic_id=data.get("originClinicId"),
                scheduled_date=data["scheduledDate"],
                scheduled_time=data["scheduledTime"],
                duration_minutes=data.get("durationMinutes"),
                contact_phone=data.get("contactPhone"),
                description=data.get("description"),
                diagnosis_text=data.get("diagnosisText"),
                requirements=data.get("requirements"),
                cie_codes=data.get("cieCodes"),
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "SurgeryScheduled",
            "SUCCESS",
            actor_user=user,
            resource_type="cirugias",
            resource_id=payload["id"],
            datos_antes=None,
            datos_despues={
                "status": payload["status"],
                "scheduledDate": payload["scheduledDate"].isoformat(),
                "scheduledTime": payload["scheduledTime"].isoformat(),
                "surgeonId": payload["surgeonId"],
                "surgeryTypeId": payload["surgeryTypeId"],
                "classificationId": payload["classificationId"],
                "cieCodesCount": len(payload["diagnoses"]),
            },
            meta={
                "module": "cirugias",
                "endpoint": request.path,
                "actorId": actor_id,
                "folio": payload["folio"],
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class SurgeryCancelView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, surgery_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CancelSurgerySerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY, details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, permissions = _actor_context(user)

        def audit_hook(*, resource_id, folio, datos_antes, datos_despues):
            # ESTRICTO: `raise_on_error=True` -- si esto falla, la excepcion
            # se propaga y `cancel_surgery` revierte todo el
            # `transaction.atomic()`, incluida la cancelacion ya aplicada.
            log_event(
                request,
                "SurgeryCancelled",
                "SUCCESS",
                actor_user=user,
                resource_type="cirugias",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "cirugias",
                    "endpoint": request.path,
                    "actorId": actor_id,
                    "folio": folio,
                },
                raise_on_error=True,
            )

        try:
            payload = cancel_surgery(
                surgery_id,
                reason_id=serializer.validated_data["reasonId"],
                notes=serializer.validated_data.get("notes"),
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class SurgeryReportView(APIView):
    """Informe de cirugias agendadas en un rango de fechas (default: hoy)."""

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

        surgery_status = request.query_params.get("status") or None
        if surgery_status and surgery_status not in SurgerySchedule.Status.values:
            return error_response(
                "VALIDATION_ERROR", "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"status": [f"Debe ser uno de: {', '.join(SurgerySchedule.Status.values)}"]},
                request_id=get_request_id(request),
            )

        _, permissions = _actor_context(user)

        try:
            payload = get_surgery_report(
                fecha_inicio, fecha_fin, permissions=permissions, status=surgery_status,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        if request.query_params.get("export") == "xlsx":
            content = build_surgery_report_workbook(payload["items"])
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            filename = f"informe_cirugias_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.xlsx"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return Response(payload, status=status.HTTP_200_OK)
