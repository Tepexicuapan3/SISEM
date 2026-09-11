import logging

from django.utils.decorators import method_decorator
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
from apps.realtime.events import (
    publish_visit_closed,
    publish_visit_diagnosis_saved,
    publish_visit_prescriptions_saved,
    publish_visit_status_changed,
)
from apps.recepcion.services.errors import VisitDomainError

from .serializers import (
    AddPrescriptionItemSerializer,
    AddSecondaryDiagnosisSerializer,
    ClinicalHistoryUpdateSerializer,
    CloseConsultationSerializer,
    CreateMedicalLeaveSerializer,
    CreateStudyResultSerializer,
    OdontogramToothUpdateSerializer,
    SearchCieSerializer,
    SaveDiagnosisSerializer,
    SavePrescriptionsSerializer,
    StartConsultationSerializer,
    StomatologyHistoryUpdateSerializer,
)
from .uses_case.clinical_history_usecase import (
    get_clinical_history,
    upsert_clinical_history,
)
from .uses_case.consultation_usecase import (
    add_secondary_diagnosis,
    cancel_secondary_diagnosis,
    close_consultation,
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
from .uses_case.patient_history_usecase import get_patient_consultations_history
from .uses_case.prescription_item_usecase import (
    add_prescription_item,
    cancel_prescription_item,
    get_prescription_items,
)
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

        try:
            payload = start_consultation(visit_id, roles, permissions, doctor_id=actor_id)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "ConsultationStarted",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": payload.get("id"),
                "actorId": actor_id,
            },
        )

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
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "DiagnosisSaved",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": payload.get("visitId"),
                "actorId": actor_id,
            },
        )

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

        try:
            payload = upsert_clinical_history(
                no_exp,
                pk_num,
                roles,
                serializer.validated_data,
                actor_id,
                permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "ClinicalHistoryUpdated",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "noExp": no_exp,
                "pkNum": pk_num,
                "actorId": actor_id,
            },
        )

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
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "OdontogramToothUpdated",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "noExp": no_exp,
                "pkNum": pk_num,
                "toothFdi": tooth_fdi,
                "actorId": actor_id,
            },
        )

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

        try:
            payload = upsert_stomatology_history(
                no_exp,
                pk_num,
                roles,
                serializer.validated_data,
                actor_id,
                permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "StomatologyHistoryUpdated",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "noExp": no_exp,
                "pkNum": pk_num,
                "actorId": actor_id,
            },
        )

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

        try:
            payload = cancel_secondary_diagnosis(
                visit_id,
                diagnosis_id,
                roles,
                doctor_id=actor_id,
                permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "SecondaryDiagnosisCancelled",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "diagnosisId": diagnosis_id,
                "actorId": actor_id,
            },
        )

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

        log_event(
            request,
            "PrescriptionItemAdded",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "actorId": actor_id,
            },
        )

        return Response(payload, status=status.HTTP_201_CREATED)


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

        try:
            payload = cancel_prescription_item(
                visit_id, item_id, roles, actor_id=actor_id, permissions=permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "PrescriptionItemCancelled",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_id,
                "itemId": item_id,
                "actorId": actor_id,
            },
        )

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

        try:
            payload = save_prescriptions(
                visit_id,
                roles,
                serializer.validated_data["items"],
                actor_id,
                permissions,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        log_event(
            request,
            "PrescriptionsSaved",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": payload.get("visitId"),
                "actorId": actor_id,
            },
        )

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
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        visit_payload = payload.get("visit", {})

        log_event(
            request,
            "ConsultationClosed",
            "SUCCESS",
            actor_user=user,
            meta={
                "module": "consulta_medica",
                "endpoint": request.path,
                "visitId": visit_payload.get("id"),
                "actorId": actor_id,
            },
        )

        _emit_visit_closed_event(
            request,
            visit_id=visit_payload.get("id"),
        )

        return Response(payload, status=status.HTTP_200_OK)
