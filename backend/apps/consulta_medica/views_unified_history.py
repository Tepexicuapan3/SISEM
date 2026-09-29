"""
Endpoints de la historia clinica unificada (antecedentes, habitos,
tratamientos dentales, notas historicas, exploracion fisica, catalogos,
estado de alergias, versiones de odontograma). Reusa los helpers de
autenticacion/CSRF/auditoria de `views.py` para mantener el mismo contrato
de errores que el resto del modulo.
"""
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.audit_service import log_event
from apps.authentication.services.response_service import error_response, get_request_id
from apps.recepcion.services.errors import VisitDomainError

from .models import HistoricalNote, SpecialtySource
from .serializers import (
    AllergyStatusSerializer,
    DentalTreatmentWriteSerializer,
    FamilyHistoryWriteSerializer,
    HabitWriteSerializer,
    PersonalHistoryWriteSerializer,
    PhysicalExamSaveSerializer,
    RecordDeactivateSerializer,
    SurgicalHistoryWriteSerializer,
)
from .services.record_access_audit_service import (
    RecordSection,
    log_patient_record_access,
    log_patient_record_change,
)
from .uses_case.odontogram_usecase import list_odontogram_versions
from .uses_case.patient_record_usecase import (
    DENTAL_TREATMENT,
    FAMILY_HISTORY,
    HABIT,
    PERSONAL_HISTORY,
    SURGICAL_HISTORY,
    create_record,
    deactivate_record,
    list_records,
    update_record,
)
from .uses_case.unified_history_usecase import (
    change_allergy_status,
    get_clinical_catalogs,
    get_physical_exam,
    list_historical_notes,
    save_physical_exam,
)
from .views import (
    _actor_context,
    _auth_or_error,
    _csrf_or_error,
    _domain_error_response,
    _log_sensitive_diagnosis_redaction_if_any,
    _parse_pk_num,
)


def _validation_error(request, details):
    return error_response(
        "VALIDATION_ERROR",
        "Hay errores en el formulario",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=details,
        request_id=get_request_id(request),
    )


def _pk_num_or_error(request):
    pk_num = _parse_pk_num(request)
    if pk_num is None:
        return None, _validation_error(request, {"pkNum": ["pkNum debe ser un numero entero."]})
    return pk_num, None


def _audit(request, user, *, action, resource_id, datos_antes, datos_despues, meta, strict=True):
    log_event(
        request,
        action,
        "SUCCESS",
        actor_user=user,
        resource_type="consulta_medica",
        resource_id=resource_id,
        datos_antes=datos_antes,
        datos_despues=datos_despues,
        meta={"module": "consulta_medica", "endpoint": request.path, **meta},
        raise_on_error=strict,
    )


class _PatientRecordCollectionView(APIView):
    """GET lista / POST crea un registro permanente del paciente."""

    authentication_classes = []
    permission_classes = []
    spec = None
    write_serializer = None
    section = None

    def get(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return error

        actor_id, roles, permissions = _actor_context(user)
        try:
            payload = list_records(self.spec, no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        restricted_ids = [item["id"] for item in payload["items"] if item.get("isRestricted")]
        _log_sensitive_diagnosis_redaction_if_any(
            request, user, actor_id=actor_id, no_exp=no_exp, pk_num=pk_num, resource_ids=restricted_ids,
            section=self.section,
        )
        log_patient_record_access(
            request, user, actor_id=actor_id, no_exp=no_exp, pk_num=pk_num, section=self.section,
        )
        payload.pop("restrictedCount", None)
        return Response(payload, status=status.HTTP_200_OK)

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

        serializer = self.write_serializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        actor_id, roles, permissions = _actor_context(user)
        meta = {"noExp": no_exp, "pkNum": pk_num, "actorId": actor_id}

        def audit_hook(*, action, resource_id, datos_antes, datos_despues):
            _audit(request, user, action=action, resource_id=resource_id,
                   datos_antes=datos_antes, datos_despues=datos_despues, meta=meta)

        try:
            payload = create_record(
                self.spec, no_exp, pk_num, roles, serializer.validated_data, actor_id, permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        log_patient_record_change(
            request, user, no_exp=no_exp, pk_num=pk_num, section=self.section,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class _PatientRecordDetailView(APIView):
    """PATCH edita / DELETE da de baja (motivo obligatorio en el body)."""

    authentication_classes = []
    permission_classes = []
    spec = None
    write_serializer = None
    section = None

    def _prepare(self, request):
        user, error = _auth_or_error(request)
        if error:
            return None, None, error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return None, None, csrf_error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return None, None, error
        return user, pk_num, None

    def _audit_hook(self, request, user, meta):
        def audit_hook(*, action, resource_id, datos_antes, datos_despues):
            _audit(request, user, action=action, resource_id=resource_id,
                   datos_antes=datos_antes, datos_despues=datos_despues, meta=meta)
        return audit_hook

    def patch(self, request, no_exp, record_id):
        user, pk_num, error = self._prepare(request)
        if error:
            return error
        serializer = self.write_serializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        actor_id, roles, permissions = _actor_context(user)
        meta = {"noExp": no_exp, "pkNum": pk_num, "actorId": actor_id}
        try:
            payload = update_record(
                self.spec, no_exp, pk_num, record_id, roles, serializer.validated_data, actor_id,
                permissions, audit_hook=self._audit_hook(request, user, meta),
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        log_patient_record_change(
            request, user, no_exp=no_exp, pk_num=pk_num, section=self.section,
        )
        return Response(payload, status=status.HTTP_200_OK)

    def delete(self, request, no_exp, record_id):
        user, pk_num, error = self._prepare(request)
        if error:
            return error
        serializer = RecordDeactivateSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        actor_id, roles, permissions = _actor_context(user)
        meta = {"noExp": no_exp, "pkNum": pk_num, "actorId": actor_id}
        try:
            payload = deactivate_record(
                self.spec, no_exp, pk_num, record_id, roles, serializer.validated_data["reason"],
                actor_id, permissions, audit_hook=self._audit_hook(request, user, meta),
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        log_patient_record_change(
            request, user, no_exp=no_exp, pk_num=pk_num, section=self.section,
        )
        return Response(payload, status=status.HTTP_200_OK)


def _record_views(spec, write_serializer, section):
    collection = method_decorator(csrf_exempt, name="dispatch")(
        type(f"{spec.audit_name}CollectionView", (_PatientRecordCollectionView,), {
            "spec": spec, "write_serializer": write_serializer, "section": section,
        })
    )
    detail = method_decorator(csrf_exempt, name="dispatch")(
        type(f"{spec.audit_name}DetailView", (_PatientRecordDetailView,), {
            "spec": spec, "write_serializer": write_serializer, "section": section,
        })
    )
    return collection, detail


PersonalHistoryCollectionView, PersonalHistoryDetailView = _record_views(
    PERSONAL_HISTORY, PersonalHistoryWriteSerializer, RecordSection.PERSONAL_HISTORY,
)
FamilyHistoryCollectionView, FamilyHistoryDetailView = _record_views(
    FAMILY_HISTORY, FamilyHistoryWriteSerializer, RecordSection.FAMILY_HISTORY,
)
SurgicalHistoryCollectionView, SurgicalHistoryDetailView = _record_views(
    SURGICAL_HISTORY, SurgicalHistoryWriteSerializer, RecordSection.SURGICAL_HISTORY,
)
HabitCollectionView, HabitDetailView = _record_views(
    HABIT, HabitWriteSerializer, RecordSection.HABITS,
)
DentalTreatmentCollectionView, DentalTreatmentDetailView = _record_views(
    DENTAL_TREATMENT, DentalTreatmentWriteSerializer, RecordSection.DENTAL_TREATMENTS,
)


class PatientHistoricalNotesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return error

        section = request.query_params.get("section") or None
        specialty = request.query_params.get("specialty") or None
        if section and section not in HistoricalNote.Section.values:
            return _validation_error(request, {"section": ["Apartado invalido."]})
        if specialty and specialty not in SpecialtySource.values:
            return _validation_error(request, {"specialty": ["Especialidad invalida."]})

        actor_id, roles, permissions = _actor_context(user)
        try:
            payload = list_historical_notes(
                no_exp, pk_num, roles, permissions, section=section, specialty=specialty,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        log_patient_record_access(
            request, user, actor_id=actor_id, no_exp=no_exp, pk_num=pk_num,
            section=RecordSection.HISTORICAL_NOTES,
        )
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VisitPhysicalExamView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        _actor_id, roles, permissions = _actor_context(user)
        try:
            payload = get_physical_exam(visit_id, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)

    def put(self, request, visit_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error

        serializer = PhysicalExamSaveSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues):
            _audit(request, user, action="PhysicalExamSaved", resource_id=resource_id,
                   datos_antes=datos_antes, datos_despues=datos_despues,
                   meta={"visitId": visit_id, "actorId": actor_id})

        try:
            payload = save_physical_exam(
                visit_id, roles, serializer.validated_data["findings"], actor_id, permissions,
                audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)


class ClinicalCatalogsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, error = _auth_or_error(request)
        if error:
            return error
        _actor_id, roles, permissions = _actor_context(user)
        try:
            payload = get_clinical_catalogs(roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PatientAllergyStatusView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, no_exp, allergy_id):
        user, error = _auth_or_error(request)
        if error:
            return error
        csrf_error = _csrf_or_error(request)
        if csrf_error:
            return csrf_error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return error

        serializer = AllergyStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(request, serializer.errors)

        actor_id, roles, permissions = _actor_context(user)

        def audit_hook(*, resource_id, datos_antes, datos_despues, strict=True):
            _audit(request, user, action="AllergyStatusChanged", resource_id=resource_id,
                   datos_antes=datos_antes, datos_despues=datos_despues,
                   meta={"noExp": no_exp, "pkNum": pk_num, "actorId": actor_id}, strict=strict)

        try:
            payload = change_allergy_status(
                no_exp, pk_num, allergy_id, roles,
                status=serializer.validated_data["status"],
                reason=serializer.validated_data["reason"],
                actor_id=actor_id, permissions=permissions, audit_hook=audit_hook,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        log_patient_record_change(
            request, user, no_exp=no_exp, pk_num=pk_num, section=RecordSection.ALLERGIES,
        )
        return Response(payload, status=status.HTTP_200_OK)


class PatientOdontogramVersionsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, no_exp):
        user, error = _auth_or_error(request)
        if error:
            return error
        pk_num, error = _pk_num_or_error(request)
        if error:
            return error
        _actor_id, roles, permissions = _actor_context(user)
        try:
            payload = list_odontogram_versions(no_exp, pk_num, roles, permissions)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)
        return Response(payload, status=status.HTTP_200_OK)
