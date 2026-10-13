"""
Vistas del import masivo de médicos por Excel (plantilla + preview +
confirmar). Transporte HTTP delgado -- toda la lógica de parseo/validación
vive en `apps.medicos.services.medico_import_service` y el alta real en
`apps.medicos.uses_case.import_medicos`.

Reusa los helpers privados de autenticación/auditoría de `rbac_views.py`
(mismo patrón que `apps.administracion.views.user_import_views`).

El confirm es ASÍNCRONO (igual que el de usuarios): guarda el archivo en un
`MedicoImportJob`, encola la tarea Celery `procesar_import_medicos` y
responde 202 con el `jobId`. El frontend consulta
`GET /medicos/import/jobs/<jobId>` hasta que el job termina.
"""

from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.views.rbac_views import _audit, _authorize, _request_id
from apps.authentication.services.response_service import error_response
from apps.medicos.models import MedicoImportJob
from apps.medicos.services import import_job_progress
from apps.medicos.services.medico_import_service import ImportFileError
from apps.medicos.tasks import procesar_import_medicos
from apps.medicos.uses_case.import_medicos import (
    PreviewMedicosImportUseCase,
    TemplateMedicosImportUseCase,
)

IMPORT_PERMISSION = "admin:gestion:medicos:create"

# Un job PENDING/RUNNING más viejo que esto se considera huérfano (worker
# caído a mitad) y deja de bloquear nuevos imports. Holgado: ~2700 médicos
# sin hasheo ni correos tardan del orden de minutos.
ACTIVE_JOB_WINDOW = timedelta(hours=1)

# Un job que sigue PENDING (el worker nunca lo tomó) pasado este tiempo se da
# por perdido: worker apagado o sin la tarea registrada (Celery no se recarga
# solo al cambiar código). Se cierra en ERROR para no bloquear una hora.
PENDING_STALE_AFTER = timedelta(minutes=5)
WORKER_UNAVAILABLE_MESSAGE = (
    "El servidor no tomó la importación (worker de Celery apagado o sin la "
    "tarea registrada). No se creó ningún médico. Reinicia el worker y vuelve "
    "a intentarlo."
)


def _expire_stale_pending(**filters) -> int:
    """Cierra en ERROR los jobs PENDING que el worker nunca tomó."""
    return MedicoImportJob.objects.filter(
        status=MedicoImportJob.Status.PENDING,
        fch_inicio__isnull=True,
        fch_alta__lt=timezone.now() - PENDING_STALE_AFTER,
        **filters,
    ).update(
        status=MedicoImportJob.Status.ERROR,
        phase=MedicoImportJob.Phase.DONE,
        error_code="WORKER_NO_DISPONIBLE",
        error_message=WORKER_UNAVAILABLE_MESSAGE,
        fch_fin=timezone.now(),
        file_content=None,
    )


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

        # Un solo import a la vez (además del lock de `cat_medicos` dentro de
        # la tarea). Ventana acotada para que un job huérfano (worker muerto a
        # mitad) no bloquee los imports para siempre.
        _expire_stale_pending()
        active_since = timezone.now() - ACTIVE_JOB_WINDOW
        active_job = MedicoImportJob.objects.filter(
            status__in=(MedicoImportJob.Status.PENDING, MedicoImportJob.Status.RUNNING),
            fch_alta__gte=active_since,
        ).first()
        if active_job is not None:
            return error_response(
                "IMPORT_IN_PROGRESS",
                "Ya hay una importación de médicos en curso. Espera a que termine.",
                status.HTTP_409_CONFLICT,
                details={"jobId": str(active_job.id)},
                request_id=_request_id(request),
            )

        job = MedicoImportJob.objects.create(
            actor=actor,
            file_name=(file.name or "import.xlsx")[:255],
            file_content=file.read(),
        )
        # on_commit: el worker no debe ver el job antes de que exista en la BD.
        transaction.on_commit(lambda: procesar_import_medicos.delay(str(job.id)))

        _audit(
            request,
            "MEDICO_IMPORT_CONFIRM",
            "medico",
            result="SUCCESS",
            after={"jobId": str(job.id), "queued": True},
        )
        return Response(serialize_job(job), status=status.HTTP_202_ACCEPTED)


class MedicoImportJobStatusView(APIView):
    """Estado/avance de un import en segundo plano (polling del frontend)."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, job_id):
        _, auth_error = _authorize(request, IMPORT_PERMISSION)
        if auth_error:
            return auth_error

        # El polling también cierra el job si el worker nunca lo tomó: así el
        # diálogo deja de esperar y muestra el error.
        _expire_stale_pending(id=job_id)
        job = MedicoImportJob.objects.defer("file_content").filter(id=job_id).first()
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
    else:
        # Mientras corre, el avance vivo está en la cache (la fase SAVING va
        # dentro de la transacción y no se refleja en el job hasta el commit).
        live = import_job_progress.get_progress(job.id)
        if live:
            payload.update(live)
    return payload
