"""
Vistas del import masivo de usuarios por Excel (plantilla + preview +
confirmar). Transporte HTTP delgado -- toda la logica de parseo/validacion
vive en `apps.administracion.services.user_import_service` y el alta real en
`apps.administracion.use_cases.users.create_user`/`import_users`.

El confirm es ASINCRONO: guarda el archivo en un `UserImportJob`, encola la
tarea Celery `procesar_import_usuarios` y responde 202 con el `jobId`. El
frontend consulta `GET /users/import/jobs/<jobId>` hasta que el job termina.
(Antes era sincrono y un lote de ~3000 usuarios excedia todo timeout HTTP.)

Reusa los helpers privados de autenticacion/auditoria de `rbac_views.py`
(mismo patron ya usado por `expediente_view.py` y las vistas de
`rbac_role_permission_*`).
"""

from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.models import UserImportJob
from apps.administracion.services.user_import_service import ImportFileError
from apps.administracion.tasks import procesar_import_usuarios
from apps.administracion.use_cases.users.import_users import (
    PreviewUsersImportUseCase,
    TemplateUsersImportUseCase,
)
from apps.administracion.views.rbac_views import _audit, _authorize, _request_id
from apps.authentication.services.response_service import error_response

IMPORT_PERMISSION = "admin:gestion:usuarios:create"

# Un job PENDING/RUNNING mas viejo que esto se considera huerfano (worker
# caido a mitad) y deja de bloquear nuevos imports. Holgado: 3000+ usuarios
# con correos tarda del orden de 30-60 min.
ACTIVE_JOB_WINDOW = timedelta(hours=3)


class UserImportTemplateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, IMPORT_PERMISSION)
        if auth_error:
            return auth_error

        content = TemplateUsersImportUseCase().execute()
        filename = f"plantilla_usuarios_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class UserImportPreviewView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _, auth_error = _authorize(request, IMPORT_PERMISSION, require_csrf=True)
        if auth_error:
            _audit(
                request,
                "RBAC_USER_IMPORT_PREVIEW",
                "user",
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
            result = PreviewUsersImportUseCase().execute(file)
        except ImportFileError as exc:
            _audit(
                request,
                "RBAC_USER_IMPORT_PREVIEW",
                "user",
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
            "RBAC_USER_IMPORT_PREVIEW",
            "user",
            result="SUCCESS",
            after={
                "totalRecords": result["totalRecords"],
                "totalErrores": result["totalErrores"],
            },
        )
        return Response(result, status=status.HTTP_200_OK)


class UserImportConfirmView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        actor, auth_error = _authorize(request, IMPORT_PERMISSION, require_csrf=True)
        if auth_error:
            _audit(
                request,
                "RBAC_USER_IMPORT_CONFIRM",
                "user",
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

        # Un solo import a la vez: dos lotes validados en paralelo pasarian
        # la validacion de unicidad y el segundo reventaria en el commit.
        # Ventana acotada para que un job huerfano (worker muerto a mitad)
        # no bloquee los imports para siempre.
        active_since = timezone.now() - ACTIVE_JOB_WINDOW
        active_job = UserImportJob.objects.filter(
            status__in=(UserImportJob.Status.PENDING, UserImportJob.Status.RUNNING),
            fch_alta__gte=active_since,
        ).first()
        if active_job is not None:
            return error_response(
                "IMPORT_IN_PROGRESS",
                "Ya hay una importación de usuarios en curso. Espera a que termine.",
                status.HTTP_409_CONFLICT,
                details={"jobId": str(active_job.id)},
                request_id=_request_id(request),
            )

        job = UserImportJob.objects.create(
            actor=actor,
            file_name=(file.name or "import.xlsx")[:255],
            file_content=file.read(),
        )
        # on_commit: el worker no debe ver el job antes de que exista en la BD.
        transaction.on_commit(lambda: procesar_import_usuarios.delay(str(job.id)))

        _audit(
            request,
            "RBAC_USER_IMPORT_CONFIRM",
            "user",
            result="SUCCESS",
            after={"jobId": str(job.id), "queued": True},
        )
        return Response(serialize_job(job), status=status.HTTP_202_ACCEPTED)


class UserImportJobStatusView(APIView):
    """Estado/avance de un import en segundo plano (polling del frontend)."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, job_id):
        _, auth_error = _authorize(request, IMPORT_PERMISSION)
        if auth_error:
            return auth_error

        job = UserImportJob.objects.defer("file_content").filter(id=job_id).first()
        if job is None:
            return error_response(
                "IMPORT_JOB_NOT_FOUND",
                "No existe la importación solicitada.",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )
        return Response(serialize_job(job), status=status.HTTP_200_OK)


def serialize_job(job):
    payload = {
        "jobId": str(job.id),
        "status": job.status,
        "phase": job.phase,
        "processed": job.processed,
        "phaseTotal": job.phase_total,
        "totalRecords": job.total_records,
        "inserted": job.inserted,
        "errorCode": job.error_code,
        "errorMessage": job.error_message,
        "createdAt": job.fch_alta.isoformat() if job.fch_alta else None,
        "startedAt": job.fch_inicio.isoformat() if job.fch_inicio else None,
        "finishedAt": job.fch_fin.isoformat() if job.fch_fin else None,
        "result": None,
    }
    if job.is_final:
        payload["result"] = job.get_result()
    return payload
