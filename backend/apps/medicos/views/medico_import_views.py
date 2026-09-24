"""
Vistas del import masivo de médicos por Excel (plantilla + preview +
confirmar). Transporte HTTP delgado -- toda la lógica de parseo/validación
vive en `apps.medicos.services.medico_import_service` y el alta real en
`apps.medicos.uses_case.import_medicos`.

Reusa los helpers privados de autenticación/auditoría de `rbac_views.py`
(mismo patrón que `apps.administracion.views.user_import_views`).
"""

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.views.rbac_views import _audit, _authorize, _request_id
from apps.authentication.services.response_service import error_response
from apps.medicos.services.medico_import_service import ImportFileError
from apps.medicos.uses_case.import_medicos import (
    ConfirmMedicosImportUseCase,
    MedicoImportRaceError,
    PreviewMedicosImportUseCase,
    TemplateMedicosImportUseCase,
)

IMPORT_PERMISSION = "admin:gestion:medicos:create"


class MedicoImportTemplateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, IMPORT_PERMISSION)
        if auth_error:
            return auth_error

        content = TemplateMedicosImportUseCase().execute()
        filename = f"plantilla_medicos_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class MedicoImportPreviewView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _, auth_error = _authorize(request, IMPORT_PERMISSION, require_csrf=True)
        if auth_error:
            _audit(
                request,
                "MEDICO_IMPORT_PREVIEW",
                "medico",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        file = request.FILES.get("file")
        if not file:
            return error_response(
                "VALIDATION_ERROR",
                "Archivo requerido",
                status.HTTP_400_BAD_REQUEST,
                details={"file": ["Campo requerido"]},
                request_id=_request_id(request),
            )

        try:
            result = PreviewMedicosImportUseCase().execute(file)
        except ImportFileError as exc:
            _audit(
                request,
                "MEDICO_IMPORT_PREVIEW",
                "medico",
                result="FAIL",
                error_code=exc.code,
            )
            return error_response(
                exc.code,
                exc.message,
                status.HTTP_400_BAD_REQUEST,
                details=exc.details,
                request_id=_request_id(request),
            )

        _audit(
            request,
            "MEDICO_IMPORT_PREVIEW",
            "medico",
            result="SUCCESS",
            after={
                "totalRecords": result["totalRecords"],
                "totalErrores": result["totalErrores"],
            },
        )
        return Response(result, status=status.HTTP_200_OK)


class MedicoImportConfirmView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        actor, auth_error = _authorize(request, IMPORT_PERMISSION, require_csrf=True)
        if auth_error:
            _audit(
                request,
                "MEDICO_IMPORT_CONFIRM",
                "medico",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        file = request.FILES.get("file")
        if not file:
            return error_response(
                "VALIDATION_ERROR",
                "Archivo requerido",
                status.HTTP_400_BAD_REQUEST,
                details={"file": ["Campo requerido"]},
                request_id=_request_id(request),
            )

        try:
            result = ConfirmMedicosImportUseCase().execute(file, actor)
        except ImportFileError as exc:
            _audit(
                request,
                "MEDICO_IMPORT_CONFIRM",
                "medico",
                result="FAIL",
                error_code=exc.code,
            )
            return error_response(
                exc.code,
                exc.message,
                status.HTTP_400_BAD_REQUEST,
                details=exc.details,
                request_id=_request_id(request),
            )
        except MedicoImportRaceError as exc:
            _audit(
                request,
                "MEDICO_IMPORT_CONFIRM",
                "medico",
                result="FAIL",
                error_code="MEDICO_IMPORT_RACE",
            )
            return error_response(
                "MEDICO_IMPORT_RACE",
                (
                    "No se pudo completar el import: el usuario de la fila "
                    f"{exc.row_number} ({exc.usuario}) ya no existe o cambió "
                    "de estado. No se creó ningún médico."
                ),
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=_request_id(request),
            )

        has_errors = result.pop("has_errors", False)
        if has_errors:
            _audit(
                request,
                "MEDICO_IMPORT_CONFIRM",
                "medico",
                result="FAIL",
                error_code="IMPORT_HAS_ERRORS",
            )
            return Response(
                {**result, "code": "IMPORT_HAS_ERRORS"},
                status=status.HTTP_409_CONFLICT,
            )

        _audit(
            request,
            "MEDICO_IMPORT_CONFIRM",
            "medico",
            result="SUCCESS",
            after={"inserted": result["inserted"]},
        )
        return Response(result, status=status.HTTP_200_OK)
