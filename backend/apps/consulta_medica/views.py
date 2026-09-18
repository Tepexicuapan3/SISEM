import logging

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.audit_service import log_event
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.catalogos.models import Medicamentos
from apps.realtime.events import (
    publish_visit_closed,
    publish_visit_diagnosis_saved,
    publish_visit_prescription_authorization_rejected,
    publish_visit_prescriptions_saved,
    publish_visit_status_changed,
)
from apps.recepcion.services.errors import VisitDomainError

from .serializers import (
    AddConsultationAddendumSerializer,
    AddPrescriptionItemSerializer,
    AddSecondaryDiagnosisSerializer,
    ClinicalHistoryUpdateSerializer,
    CloseConsultationSerializer,
    CreateMedicalLeaveSerializer,
    CreateStudyResultSerializer,
    OdontogramToothUpdateSerializer,
    RejectPrescriptionAuthorizationSerializer,
    SearchCieSerializer,
    SaveDiagnosisSerializer,
    SavePrescriptionsSerializer,
    StartConsultationSerializer,
    StomatologyHistoryUpdateSerializer,
)
from .services.report_export_service import build_daily_report_workbook
from .services.report_export_service_medical_leave import build_medical_leave_report_workbook
from .uses_case.daily_report_usecase import get_daily_consultation_report
from .uses_case.medical_leave_report_usecase import get_medical_leave_report
from .uses_case.clinical_history_usecase import (
    get_clinical_history,
    upsert_clinical_history,
)
from .uses_case.consultation_usecase import (
    add_consultation_addendum,
    add_secondary_diagnosis,
    cancel_secondary_diagnosis,
    close_consultation,
    get_consultation_addenda,
    get_secondary_diagnoses,
    save_diagnosis,
    save_prescriptions,
    search_cies,
    start_consultation,
)
from .uses_case.medical_leave_usecase import (
    create_medical_leave,
    get_patient_medical_leaves,
)
from .uses_case.patient_history_usecase import (
    get_patient_consultations_history,
    get_patient_legacy_consultations_history,
)
from .uses_case.prescription_item_usecase import (
    add_prescription_item,
    authorize_prescription,
    cancel_prescription_item,
    get_prescription_items,
    list_pending_prescription_authorizations,
    list_prescription_authorizations_history,
    reject_prescription,
)
from .repositories.prescription_repository import PrescriptionRepository
from .uses_case.study_result_usecase import (
    create_study_result,
    get_patient_study_results,
)
from .uses_case.stomatology_history_usecase import (
    get_stomatology_history,
    upsert_stomatology_history,
)
from .uses_case.odontogram_usecase import (
    get_patient_odontogram,
    upsert_tooth_condition,
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


def _emit_visit_status_changed_event(request, *, visit_id, status):
    request_id = get_request_id(request)

    try:
        publish_visit_status_changed(
            visit_id=visit_id,
            status=status,
            request_id=request_id,
            correlation_id=request_id,
        )
    except Exception:
        logger.exception(
            "No se pudo publicar evento realtime de inicio de consulta",
            extra={"visit_id": visit_id, "status": status, "request_id": request_id},
        )


def _emit_visit_closed_event(request, *, visit_id):
    request_id = get_request_id(request)

    try:
        publish_visit_closed(
            visit_id=visit_id,
            request_id=request_id,
            correlation_id=request_id,
        )
    except Exception:
        logger.exception(
            "No se pudo publicar evento realtime de cierre de consulta",
            extra={"visit_id": visit_id, "request_id": request_id},
        )


def _emit_visit_diagnosis_saved_event(
    request,
    *,
    visit_id,
    status,
    primary_diagnosis,
    final_note,
    cie_code,
):
    request_id = get_request_id(request)

    try:
        publish_visit_diagnosis_saved(
            visit_id=visit_id,
            status=status,
            primary_diagnosis=primary_diagnosis,
            final_note=final_note,
            cie_code=cie_code,
            request_id=request_id,
            correlation_id=request_id,
        )
    except Exception:
        logger.exception(
            "No se pudo publicar evento realtime de diagnostico",
            extra={"visit_id": visit_id, "request_id": request_id},
        )


def _emit_visit_prescriptions_saved_event(
    request,
    *,
    visit_id,
    status,
    items,
):
    request_id = get_request_id(request)

    try:
        publish_visit_prescriptions_saved(
            visit_id=visit_id,
            status=status,
            items=items,
            request_id=request_id,
            correlation_id=request_id,
        )
    except Exception:
        logger.exception(
            "No se pudo publicar evento realtime de receta",
            extra={"visit_id": visit_id, "request_id": request_id},
        )


def _emit_prescription_authorization_rejected_event(
    request, *, visit_id, authorization_id, reason,
):
    request_id = get_request_id(request)

    try:
        publish_visit_prescription_authorization_rejected(
            visit_id=visit_id,
            authorization_id=authorization_id,
            reason=reason,
            request_id=request_id,
            correlation_id=request_id,
        )
    except Exception:
        logger.exception(
            "No se pudo publicar evento realtime de rechazo de autorizacion de receta",
            extra={
                "visit_id": visit_id,
                "authorization_id": authorization_id,
                "request_id": request_id,
            },
        )


@method_decorator(csrf_exempt, name="dispatch")
class VisitConsultationStartView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = StartConsultationSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        # A7: camino critico de consulta -- audit_hook con strict=False, un
        # fallo del logger no bloquea la atencion al paciente.
        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "ConsultationStarted",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "visitId": resource_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = start_consultation(
                visit_id, roles, permissions, doctor_id=actor_id, audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        _emit_visit_status_changed_event(
            request,
            visit_id=payload.get("id"),
            status=payload.get("status"),
        )

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitDiagnosisSaveView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = SaveDiagnosisSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        # A7: camino critico de consulta -- audit_hook con strict=False.
        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "DiagnosisSaved",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "visitId": visit_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = save_diagnosis(
                visit_id,
                roles,
                serializer.validated_data["primaryDiagnosis"],
                serializer.validated_data["finalNote"],
                actor_id,
                permissions,
                serializer.validated_data.get("cieCode"),
                serializer.validated_data.get("subjective"),
                serializer.validated_data.get("objective"),
                serializer.validated_data.get("assessment"),
                serializer.validated_data.get("plan"),
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        _emit_visit_diagnosis_saved_event(
            request,
            visit_id=payload.get("visitId"),
            status=payload.get("status"),
            primary_diagnosis=payload.get("primaryDiagnosis"),
            final_note=payload.get("finalNote"),
            cie_code=payload.get("cieCode"),
        )

        return Response(payload, status=status.HTTP_200_OK)


def _parse_pk_num(request):
    raw_value = request.query_params.get("pkNum", "0")
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


@method_decorator(csrf_exempt, name="dispatch")
class PatientClinicalHistoryView(APIView):
    """
    Historia Clinica General de un paciente/familiar (no_exp + pk_num).
    NO cuelga de una visita especifica -- a diferencia del resto de este
    modulo (diagnostico, receta), es un solo registro por paciente que se
    consulta/edita desde el Expediente, con o sin visita activa.
    """

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
            payload = get_clinical_history(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)

    def patch(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        pk_num = _parse_pk_num(request)
        if pk_num is None:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"pkNum": ["pkNum debe ser un numero entero."]},
                request_id=get_request_id(request),
            )

        serializer = ClinicalHistoryUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "ClinicalHistoryUpdated",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "noExp": no_exp,
                    "pkNum": pk_num,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = upsert_clinical_history(
                no_exp,
                pk_num,
                roles,
                serializer.validated_data,
                actor_id,
                permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitMedicalLeaveCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CreateMedicalLeaveSerializer(data=request.data)
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
            payload = create_medical_leave(
                visit_id,
                roles,
                leave_type_id=data["leaveTypeId"],
                days=data["days"],
                start_date=data["startDate"],
                is_subsequent=data["isSubsequent"],
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "MedicalLeaveCreated",
            "SUCCESS",
            actor_user=user,
            resource_type="consulta_medica",
            resource_id=payload.get("id"),
            datos_antes=None,
            datos_despues={
                "visitId": visit_id,
                "folio": payload.get("folio"),
                "leaveTypeId": payload.get("leaveTypeId"),
                "leaveTypeName": payload.get("leaveTypeName"),
                "days": payload.get("days"),
                "isSubsequent": payload.get("isSubsequent"),
                "startDate": (
                    payload["startDate"].isoformat() if payload.get("startDate") else None
                ),
                "endDate": payload["endDate"].isoformat() if payload.get("endDate") else None,
            },
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class PatientMedicalLeavesHistoryView(APIView):
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
            payload = get_patient_medical_leaves(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientConsultationsHistoryView(APIView):
    """
    Historial de consultas cerradas de un paciente/familiar (no_exp + pk_num),
    a traves de todas sus visitas -- no una sola. Complementa a
    PatientClinicalHistoryView (que es un solo registro, no un historial).
    """

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
            payload = get_patient_consultations_history(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


class PatientLegacyConsultationsHistoryView(APIView):
    """
    Historial de notas del legado (previas a SIRES) de un paciente/familiar
    -- archivo de solo lectura, ver docstring de LegacyConsultationRecord.
    Complementa a PatientConsultationsHistoryView (consultas reales de
    SIRES, vía Visit/VisitConsultation).
    """

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
            payload = get_patient_legacy_consultations_history(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientOdontogramView(APIView):
    """
    GET devuelve el odontograma completo (todas las piezas FDI del tipo de
    denticion pedido, rellenando con "sano" las que no tienen registro).
    """

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

        dentition = request.query_params.get("dentition", "permanent")
        _, roles, permissions = _actor_context(user)

        try:
            payload = get_patient_odontogram(
                no_exp, pk_num, roles, permissions, dentition=dentition,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientOdontogramToothView(APIView):
    """PATCH actualiza la condicion de UNA sola pieza dental."""

    authentication_classes = []
    permission_classes = []

    def patch(self, request, no_exp, tooth_fdi):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        pk_num = _parse_pk_num(request)
        if pk_num is None:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"pkNum": ["pkNum debe ser un numero entero."]},
                request_id=get_request_id(request),
            )

        serializer = OdontogramToothUpdateSerializer(data=request.data)
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

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "OdontogramToothUpdated",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "noExp": no_exp,
                    "pkNum": pk_num,
                    "toothFdi": tooth_fdi,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = upsert_tooth_condition(
                no_exp,
                pk_num,
                tooth_fdi,
                roles,
                condition=data["condition"],
                notes=data.get("notes"),
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientStomatologyHistoryView(APIView):
    """
    Historia Clinica de Estomatologia de un paciente/familiar. Igual que
    PatientClinicalHistoryView: un solo registro por paciente, sin visita
    asociada, editable con o sin consulta activa.
    """

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
            payload = get_stomatology_history(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)

    def patch(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        pk_num = _parse_pk_num(request)
        if pk_num is None:
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"pkNum": ["pkNum debe ser un numero entero."]},
                request_id=get_request_id(request),
            )

        serializer = StomatologyHistoryUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "StomatologyHistoryUpdated",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "noExp": no_exp,
                    "pkNum": pk_num,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = upsert_stomatology_history(
                no_exp,
                pk_num,
                roles,
                serializer.validated_data,
                actor_id,
                permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitStudyResultCreateView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CreateStudyResultSerializer(data=request.data)
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
            payload = create_study_result(
                visit_id,
                roles,
                study_type_id=data["studyTypeId"],
                result_date=data["resultDate"],
                notes=data.get("notes"),
                file=data["file"],
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "StudyResultCreated",
            "SUCCESS",
            actor_user=user,
            resource_type="consulta_medica",
            resource_id=payload.get("id"),
            datos_antes=None,
            datos_despues={
                "visitId": visit_id,
                "studyTypeId": payload.get("studyTypeId"),
                "studyTypeName": payload.get("studyTypeName"),
                "resultDate": (
                    payload["resultDate"].isoformat() if payload.get("resultDate") else None
                ),
                "hasFile": True,
                "notesLen": len(payload["notes"]) if payload.get("notes") else None,
            },
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class PatientStudyResultsHistoryView(APIView):
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
            payload = get_patient_study_results(
                no_exp, pk_num, roles, permissions, request=request
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitSecondaryDiagnosesView(APIView):
    """
    Diagnosticos secundarios/comorbilidades de una consulta -- separado del
    diagnostico PRINCIPAL (VisitDiagnosisSaveView). Equivalente moderno de
    det_hisnotcie del legado.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_secondary_diagnoses(visit_id, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = AddSecondaryDiagnosisSerializer(data=request.data)
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
            payload = add_secondary_diagnosis(
                visit_id,
                roles,
                cie_code=data["cieCode"],
                notes=data.get("notes"),
                doctor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "SecondaryDiagnosisAdded",
            "SUCCESS",
            actor_user=user,
            resource_type="consulta_medica",
            resource_id=payload.get("id"),
            datos_antes=None,
            datos_despues={
                "visitId": visit_id,
                "cieCode": payload.get("cieCode"),
                "status": payload.get("status"),
                "notesLen": len(payload["notes"]) if payload.get("notes") else None,
            },
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VisitConsultationAddendumView(APIView):
    """
    Notas de aclaracion sobre una consulta YA CERRADA (NOM-004/024:
    registro firmado no se modifica, se aclara con una anotacion nueva
    fechada y con autor). Append-only -- no hay PUT/DELETE, ver docstring
    de ConsultationAddendum.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_consultation_addenda(visit_id, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = AddConsultationAddendumSerializer(data=request.data)
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
            payload = add_consultation_addendum(
                visit_id,
                roles,
                text=serializer.validated_data["text"],
                doctor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "ConsultationAddendumAdded",
            "SUCCESS",
            actor_user=user,
            resource_type="consulta_medica",
            resource_id=payload.get("id"),
            datos_antes=None,
            datos_despues={
                "consultationId": payload.get("consultationId"),
                "textLen": len(payload["text"]) if payload.get("text") else None,
            },
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VisitSecondaryDiagnosisCancelView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, visit_id, diagnosis_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "SecondaryDiagnosisCancelled",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "visitId": visit_id,
                    "diagnosisId": diagnosis_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = cancel_secondary_diagnosis(
                visit_id,
                diagnosis_id,
                roles,
                doctor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitPrescriptionItemsView(APIView):
    """
    Items de receta estructurados (medicamento del catalogo + indicaciones
    + cantidad) -- complementa a VisitPrescriptionsSaveView (texto libre).
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_prescription_items(visit_id, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = AddPrescriptionItemSerializer(data=request.data)
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
            payload = add_prescription_item(
                visit_id,
                roles,
                medication_id=data["medicationId"],
                quantity=data["quantity"],
                indications=data["indications"],
                dose=data.get("dose"),
                actor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        # `add_prescription_item` es SIMPLE, sin audit_hook (A5) -- prescriptionId
        # y requiresAuthorization no vienen en el payload de to_contract, se
        # resuelven aca con 2 lecturas extra solo para el snapshot de
        # auditoria (mismo criterio que _maybe_create_authorization interno).
        prescription = PrescriptionRepository.get_by_visit(visit_id)
        medication = Medicamentos.objects.filter(pk=data["medicationId"]).first()
        requires_authorization = bool(
            medication is not None
            and (
                medication.cuadro_basico == Medicamentos.CuadroBasico.ESPECIAL
                or medication.is_controlled
            )
        )

        log_event(
            request,
            "PrescriptionItemAdded",
            "SUCCESS",
            actor_user=user,
            resource_type="consulta_medica",
            resource_id=payload.get("id"),
            datos_antes=None,
            datos_despues={
                "visitId": visit_id,
                "prescriptionId": prescription.id_prescription if prescription else None,
                "medicationId": payload.get("medicationId"),
                "medicationName": payload.get("medicationName"),
                "quantity": payload.get("quantity"),
                "dose": payload.get("dose"),
                "indicationsLen": (
                    len(payload["indications"]) if payload.get("indications") else None
                ),
                "requiresAuthorization": requires_authorization,
            },
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


class PrescriptionAuthorizationsPendingView(APIView):
    """
    GET /prescriptions/authorizations/pending -- cola de recetas con
    medicamentos ESPECIAL/controlados esperando autorizacion. Equivalente
    moderno de la rama de recetas de `autorizacion.jsp` (legado), sin la
    tabla `det_clinicas` ni `pw_autoriza` -- ver docstring de
    PrescriptionAuthorization.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, roles, permissions = _actor_context(user)

        try:
            payload = list_pending_prescription_authorizations(roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PrescriptionAuthorizationDecisionView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, authorization_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "PrescriptionAuthorizationApproved",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "authorizationId": authorization_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = authorize_prescription(
                authorization_id,
                roles,
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PrescriptionAuthorizationRejectView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, authorization_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = RejectPrescriptionAuthorizationSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "PrescriptionAuthorizationRejected",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "authorizationId": authorization_id,
                    "actorId": actor_id,
                    "reason": serializer.validated_data["reason"],
                },
                raise_on_error=strict,
            )

        try:
            payload = reject_prescription(
                authorization_id,
                roles,
                reason=serializer.validated_data["reason"],
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        _emit_prescription_authorization_rejected_event(
            request,
            visit_id=payload.get("visitId"),
            authorization_id=authorization_id,
            reason=serializer.validated_data["reason"],
        )

        return Response(payload, status=status.HTTP_200_OK)


class PrescriptionAuthorizationsHistoryView(APIView):
    """
    GET /prescriptions/authorizations -- historial completo (cualquier
    estatus) para auditoria NOM-024, a diferencia de
    PrescriptionAuthorizationsPendingView que solo muestra la cola activa.
    Filtros opcionales: estatus, fechaInicio, fechaFin (sobre fch_alta).
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        _, roles, permissions = _actor_context(user)

        raw_start = request.query_params.get("fechaInicio")
        raw_end = request.query_params.get("fechaFin")
        date_from = parse_date(raw_start) if raw_start else None
        date_to = parse_date(raw_end) if raw_end else None

        if (raw_start and date_from is None) or (raw_end and date_to is None):
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"fecha": ["Formato esperado: YYYY-MM-DD."]},
                request_id=get_request_id(request),
            )

        try:
            payload = list_prescription_authorizations_history(
                roles,
                permissions,
                status=request.query_params.get("estatus") or None,
                date_from=date_from,
                date_to=date_to,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitPrescriptionItemCancelView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, visit_id, item_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "PrescriptionItemCancelled",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "visitId": visit_id,
                    "itemId": item_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = cancel_prescription_item(
                visit_id,
                item_id,
                roles,
                actor_id=actor_id,
                permissions=permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitCieSearchView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error

        serializer = SearchCieSerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        _, roles, permissions = _actor_context(user)

        try:
            payload = search_cies(
                serializer.validated_data["search"],
                roles,
                permissions,
                limit=serializer.validated_data["limit"],
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitPrescriptionsSaveView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = SavePrescriptionsSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "PrescriptionsSaved",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "visitId": visit_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            payload = save_prescriptions(
                visit_id,
                roles,
                serializer.validated_data["items"],
                actor_id,
                permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        _emit_visit_prescriptions_saved_event(
            request,
            visit_id=payload.get("visitId"),
            status=payload.get("status"),
            items=payload.get("items") or [],
        )

        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitConsultationCloseView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = CloseConsultationSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        actor_id, roles, permissions = _actor_context(user)

        # A7: camino critico de consulta -- audit_hook con strict=False.
        # A4.3: los 3 return paths de close_consultation invocan este mismo
        # hook exactamente una vez cada uno (invariante: 1 evento por request).
        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            log_event(
                request,
                "ConsultationClosed",
                "SUCCESS",
                actor_user=user,
                resource_type="consulta_medica",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                meta={
                    "module": "consulta_medica",
                    "endpoint": request.path,
                    "visitId": visit_id,
                    "actorId": actor_id,
                },
                raise_on_error=strict,
            )

        try:
            validated_data = dict(serializer.validated_data)
            primary_diagnosis = validated_data.get("primaryDiagnosis", "")
            final_note = validated_data.get("finalNote", "")
            payload = close_consultation(
                visit_id,
                roles,
                primary_diagnosis,
                final_note,
                actor_id,
                permissions,
                validated_data.get("cieCode"),
                validated_data.get("subjective"),
                validated_data.get("objective"),
                validated_data.get("assessment"),
                validated_data.get("plan"),
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        visit_payload = payload.get("visit", {})

        _emit_visit_closed_event(
            request,
            visit_id=visit_payload.get("id"),
        )

        return Response(payload, status=status.HTTP_200_OK)


class DailyConsultationReportView(APIView):
    """
    Informe de consultas cerradas en un rango de fechas (default: hoy).
    Equivalente moderno de body-repconsulta.jsp ("Informe Diario de
    Consulta Medica") del legado -- ver docs/architecture/legacy-reports-inventory.md.
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

        doctor_id = request.query_params.get("doctorId") or None
        consultorio_id = request.query_params.get("consultorioId") or None

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_daily_consultation_report(
                fecha_inicio,
                fecha_fin,
                roles,
                permissions,
                doctor_id=doctor_id,
                consultorio_id=consultorio_id,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        if request.query_params.get("export") == "xlsx":
            content = build_daily_report_workbook(payload["items"])
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            filename = f"informe_diario_consulta_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.xlsx"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return Response(payload, status=status.HTTP_200_OK)


class MedicalLeaveReportView(APIView):
    """
    Informe de incapacidades/licencias con fecha de inicio en un rango
    (default: hoy). Equivalente moderno de body-repincap.jsp del legado --
    ver docs/architecture/legacy-reports-inventory.md.
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

        leave_type_id = request.query_params.get("leaveTypeId") or None
        no_exp = request.query_params.get("noExp") or None

        _, roles, permissions = _actor_context(user)

        try:
            payload = get_medical_leave_report(
                fecha_inicio,
                fecha_fin,
                roles,
                permissions,
                leave_type_id=leave_type_id,
                no_exp=no_exp,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        if request.query_params.get("export") == "xlsx":
            content = build_medical_leave_report_workbook(payload["items"])
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            filename = f"informe_incapacidades_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.xlsx"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return Response(payload, status=status.HTTP_200_OK)
