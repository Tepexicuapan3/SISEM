import logging

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
from apps.realtime.events import (
    publish_visit_cancelled,
    publish_visit_created,
    publish_visit_no_show,
    publish_visit_status_changed,
)
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.serializers import (
    CreateVisitSerializer,
    ListVisitsQuerySerializer,
    PatientLookupQuerySerializer,
    UpdateVisitStatusSerializer,
)
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_queue_usecase import (
    change_visit_status,
    create_visit,
    ensure_recepcion_role,
    ensure_visit_queue_access,
    get_visit_status_log,
    list_visits,
    lookup_patient,
    resolve_vitals_visibility,
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


def _require_recepcion_role(user):
    auth_user = UserRepository.build_auth_user(user)
    ensure_recepcion_role(
        auth_user.get("roles", []),
        auth_user.get("permissions", []),
    )


def _require_visit_queue_access(user):
    auth_user = UserRepository.build_auth_user(user)
    ensure_visit_queue_access(
        auth_user.get("roles", []),
        auth_user.get("permissions", []),
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


def _emit_visit_status_changed_event(request, *, visit_id, status, previous_status=None):
    request_id = get_request_id(request)
    try:
        publish_visit_status_changed(
            visit_id=visit_id, status=status,
            previous_status=previous_status,
            request_id=request_id, correlation_id=request_id,
        )
    except Exception:
        logger.exception("No se pudo publicar evento realtime de visita",
                         extra={"visit_id": visit_id, "status": status, "request_id": request_id})


def _emit_visit_created_event(request, *, visit_id, status):
    request_id = get_request_id(request)
    try:
        publish_visit_created(visit_id=visit_id, status=status,
                              request_id=request_id, correlation_id=request_id)
    except Exception:
        logger.exception("No se pudo publicar evento realtime de creacion de visita",
                         extra={"visit_id": visit_id, "status": status, "request_id": request_id})


def _emit_visit_cancelled_event(request, *, visit_id, status, previous_status=None):
    request_id = get_request_id(request)
    try:
        publish_visit_cancelled(visit_id=visit_id, status=status,
                                previous_status=previous_status,
                                request_id=request_id, correlation_id=request_id)
    except Exception:
        logger.exception("No se pudo publicar evento realtime de cancelacion de visita",
                         extra={"visit_id": visit_id, "status": status, "request_id": request_id})


def _emit_visit_no_show_event(request, *, visit_id, status, previous_status=None):
    request_id = get_request_id(request)
    try:
        publish_visit_no_show(visit_id=visit_id, status=status,
                              previous_status=previous_status,
                              request_id=request_id, correlation_id=request_id)
    except Exception:
        logger.exception("No se pudo publicar evento realtime de no show de visita",
                         extra={"visit_id": visit_id, "status": status, "request_id": request_id})


def _visit_error_response(request, exc):
    return error_response(exc.code, exc.message, exc.status_code,
                          details=exc.details, request_id=get_request_id(request))


# ─── Visitas ──────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class VisitsView(APIView):
    authentication_classes = []
    permission_classes     = []

    def post(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error
        try:
            _require_recepcion_role(user)
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        serializer = CreateVisitSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("VALIDATION_ERROR", "Hay errores en el formulario",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=serializer.errors, request_id=get_request_id(request))

        hora_consulta = None
        hora_raw = serializer.validated_data.get("horaConsulta")
        if hora_raw:
            try:
                from datetime import datetime as _dt
                hora_consulta = _dt.strptime(hora_raw.strip()[:5], "%H:%M").time()
            except (ValueError, AttributeError):
                pass

        try:
            visit = create_visit(
                no_exp=serializer.validated_data["noExp"],
                pk_num=serializer.validated_data.get("pkNum", 0),
                nombre_paciente=serializer.validated_data.get("nombrePaciente") or None,
                arrival_type=serializer.validated_data["arrivalType"],
                service_type=serializer.validated_data.get("serviceType"),
                appointment_id=serializer.validated_data.get("appointmentId"),
                doctor_id=serializer.validated_data.get("doctorId"),
                consultorio_id=serializer.validated_data.get("consultorioId"),
                tipo_cita_id=serializer.validated_data.get("tipoCitaId"),
                notes=serializer.validated_data.get("notes"),
                hora_consulta=hora_consulta,
                fecha_consulta=serializer.validated_data.get("fechaConsulta"),
                created_by_id=getattr(user, "id_usuario", None),
            )
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        log_event(request, "VisitCreated", "SUCCESS", actor_user=user,
                  meta={"module": "recepcion", "endpoint": request.path, "visitId": visit.get("id")})
        _emit_visit_status_changed_event(request, visit_id=visit.get("id"), status=visit.get("status"))
        _emit_visit_created_event(request, visit_id=visit.get("id"), status=visit.get("status"))
        return Response(visit, status=status.HTTP_201_CREATED)

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error
        try:
            _require_visit_queue_access(user)
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        serializer = ListVisitsQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response("VALIDATION_ERROR", "Parametros de paginacion invalidos",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=serializer.errors, request_id=get_request_id(request))

        # Narrowing de contrato (D3, somatometria-modulo-integral): recepcion
        # NO recibe valores numericos de vitals en el LIST, solo estado.
        # Rollback de emergencia (1 linea): reemplazar por `True` fijo.
        auth_user = UserRepository.build_auth_user(user)
        include_vitals_values = resolve_vitals_visibility(auth_user.get("permissions", []))

        payload = list_visits(
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["pageSize"],
            status_filter=serializer.validated_data.get("status"),
            date_filter=serializer.validated_data.get("date"),
            doctor_id=serializer.validated_data.get("doctorId"),
            consultorio_id=serializer.validated_data.get("consultorioId"),
            service_type=serializer.validated_data.get("serviceType"),
            no_exp=serializer.validated_data.get("noExp"),
            fecha_desde=serializer.validated_data.get("fechaDesde"),
            fecha_hasta=serializer.validated_data.get("fechaHasta"),
            folio=serializer.validated_data.get("folio"),
            q=serializer.validated_data.get("q"),
            pk_num=serializer.validated_data.get("pkNum"),
            include_vitals_values=include_vitals_values,
        )
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitStatusView(APIView):
    authentication_classes = []
    permission_classes     = []

    def patch(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error
        try:
            _require_recepcion_role(user)
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        serializer = UpdateVisitStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("VALIDATION_ERROR", "Hay errores en el formulario",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=serializer.errors, request_id=get_request_id(request))

        try:
            target_status   = serializer.validated_data["targetStatus"]
            previous_status = None
            current_visit   = VisitRepository.get_by_id(visit_id)
            if current_visit is not None:
                previous_status = current_visit.status
            visit = change_visit_status(
                visit_id,
                target_status,
                changed_by_id=getattr(user, "id_usuario", None),
                motivo_cancelacion=serializer.validated_data.get("motivoCancelacionId"),
                motivo_detalle=serializer.validated_data.get("motivoDetalle") or None,
            )
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        log_event(request, "VisitStatusChanged", "SUCCESS", actor_user=user,
                  meta={"module": "recepcion", "endpoint": request.path,
                        "visitId": visit.get("id"), "targetStatus": target_status})

        if target_status == "cancelada":
            log_event(request, "VisitCancelled", "SUCCESS", actor_user=user,
                      meta={"module": "recepcion", "endpoint": request.path, "visitId": visit.get("id")})
            _emit_visit_cancelled_event(request, visit_id=visit.get("id"),
                                        status=visit.get("status"), previous_status=previous_status)
        if target_status == "no_show":
            log_event(request, "VisitNoShow", "SUCCESS", actor_user=user,
                      meta={"module": "recepcion", "endpoint": request.path, "visitId": visit.get("id")})
            _emit_visit_no_show_event(request, visit_id=visit.get("id"),
                                      status=visit.get("status"), previous_status=previous_status)

        _emit_visit_status_changed_event(request, visit_id=visit.get("id"),
                                         status=visit.get("status"), previous_status=previous_status)
        return Response(visit, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientLookupView(APIView):
    """
    GET /visits/patient-lookup?noExp=12345&historico=

    Retorna titular + derechohabientes -- incluye foto (JPEG base64) desde
    2026-09-14 (antes se calculaba en buscar_expediente() y se descartaba en
    _build_member; ver PatientMember.foto). El campo `curp` tambien se
    expuso desde esa fecha, pero se removio temporalmente el 2026-09-17
    (columna inexistente en Postgres, rompia produccion -- ver
    docs/continuar-en-trabajo.md); hoy `curp` siempre llega en `None`
    (`_build_member` usa `.get("CURP") or None`, nunca falta la clave). El
    parametro `historico` (antes ignorado por este serializer -- bug real,
    corregido en la misma fecha) decide si se incluyen miembros de baja.

    NOTA DE PERFORMANCE: este endpoint tambien lo usa el selector de
    check-in de Recepcion (uso de alta frecuencia); incluir la foto de
    cada miembro del nucleo engorda la respuesta ~15-20KB por persona. Si
    eso se nota lento en el check-in, la opcion es que buscar_expediente()
    reciba un `incluir_fotos` explicito hasta este endpoint (hoy siempre
    True) para que el check-in pueda pedir `historico=False` SIN fotos, y
    solo el expediente (historico=True) las pida.
    """

    authentication_classes = []
    permission_classes     = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error
        try:
            _require_visit_queue_access(user)
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        serializer = PatientLookupQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response("VALIDATION_ERROR", "Parámetros inválidos",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=serializer.errors, request_id=get_request_id(request))

        try:
            payload = lookup_patient(
                serializer.validated_data["noExp"],
                historico=serializer.validated_data["historico"],
            )
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitStatusLogView(APIView):
    """
    GET /visits/{visit_id}/status-log

    Retorna el historial de cambios de estado de una visita.
    Requerido por NOM-024-SSA3-2012 para trazabilidad clínica.
    """

    authentication_classes = []
    permission_classes     = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        try:
            _require_visit_queue_access(user)
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        try:
            logs = get_visit_status_log(visit_id)
        except VisitDomainError as exc:
            return _visit_error_response(request, exc)

        return Response({"items": logs}, status=status.HTTP_200_OK)
