import logging
import time

from celery import shared_task
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.administracion.models import UserImportJob
from apps.administracion.services.user_import_service import ImportFileError
from apps.administracion.use_cases.users.import_users import (
    ConfirmUsersImportUseCase,
    RoleVanishedDuringImport,
)

logger = logging.getLogger(__name__)

# Throttle de escrituras de avance: sin esto, 3000 filas = 6000+ UPDATEs
# solo para la barra de progreso.
_PROGRESS_MIN_INTERVAL_S = 1.0


class _JobProgress:
    def __init__(self, job_id):
        self.job_id = job_id
        self._last_phase = None
        self._last_write = 0.0

    def __call__(self, phase, done, total):
        now = time.monotonic()
        phase_changed = phase != self._last_phase
        finished_phase = total and done >= total
        if not (phase_changed or finished_phase or now - self._last_write >= _PROGRESS_MIN_INTERVAL_S):
            return
        UserImportJob.objects.filter(id=self.job_id).update(
            phase=phase, processed=done, phase_total=total,
        )
        self._last_phase = phase
        self._last_write = now

    @property
    def last_phase(self):
        return self._last_phase


def _finish(job_id, **fields):
    UserImportJob.objects.filter(id=job_id).update(
        fch_fin=timezone.now(), file_content=None, **fields,
    )


@shared_task
def procesar_import_usuarios(job_id):
    """
    Ejecuta un `UserImportJob` (encolado por `UserImportConfirmView`).
    Misma logica todo-o-nada que el confirm sincrono de siempre: reusa
    `ConfirmUsersImportUseCase` tal cual, solo le agrega reporte de avance.

    Sin reintentos automaticos a proposito: si el worker muere a mitad, la
    transaccion del lote se revierte y el job queda RUNNING; reintentar a
    ciegas podria duplicar el envio de correos. Se vuelve a subir el archivo.
    """
    # Toma atomica del job: solo PENDING -> RUNNING, para que una entrega
    # duplicada del broker no procese el mismo archivo dos veces.
    claimed = UserImportJob.objects.filter(
        id=job_id, status=UserImportJob.Status.PENDING,
    ).update(status=UserImportJob.Status.RUNNING, fch_inicio=timezone.now())
    if not claimed:
        logger.warning("UserImportJob %s no esta PENDING; se ignora", job_id)
        return

    job = UserImportJob.objects.select_related("actor").get(id=job_id)
    file = SimpleUploadedFile(job.file_name, bytes(job.file_content))

    progress = _JobProgress(job_id)
    try:
        result = ConfirmUsersImportUseCase().execute(file, job.actor, progress=progress)
    except ImportFileError as exc:
        _finish(
            job_id,
            status=UserImportJob.Status.ERROR,
            phase=UserImportJob.Phase.DONE,
            error_code=exc.code,
            error_message=exc.message,
        )
        return
    except RoleVanishedDuringImport as exc:
        _finish(
            job_id,
            status=UserImportJob.Status.ERROR,
            phase=UserImportJob.Phase.DONE,
            error_code="ROLE_VANISHED",
            error_message=(
                "No se pudo completar el import: el rol de la fila "
                f"{exc.row_number} ({exc.username}) ya no existe o esta inactivo. "
                "No se creó ningún usuario."
            ),
        )
        return
    except Exception:
        logger.exception("UserImportJob %s fallo inesperadamente", job_id)
        # En la fase de correos el lote YA se comprometio: los usuarios existen.
        users_committed = progress.last_phase == UserImportJob.Phase.SENDING_EMAILS
        _finish(
            job_id,
            status=UserImportJob.Status.ERROR,
            phase=UserImportJob.Phase.DONE,
            error_code="IMPORT_UNEXPECTED_ERROR",
            error_message=(
                "Los usuarios se crearon, pero falló el envío de correos de credenciales. "
                "Restablece la contraseña de quienes no recibieron el correo."
                if users_committed
                else "Error inesperado al importar. No se creó ningún usuario."
            ),
        )
        return

    has_errors = result.pop("has_errors", False)
    job.set_result(result)
    _finish(
        job_id,
        status=(
            UserImportJob.Status.VALIDATION_FAILED if has_errors else UserImportJob.Status.SUCCESS
        ),
        phase=UserImportJob.Phase.DONE,
        total_records=result["totalRecords"],
        inserted=result["inserted"],
        result_json=job.result_json,
    )
    logger.info(
        "UserImportJob %s terminado: filas=%s insertados=%s errores=%s correos_fallidos=%s",
        job_id,
        result["totalRecords"],
        result["inserted"],
        result["totalErrores"],
        len(result.get("emailFailures") or []),
    )
