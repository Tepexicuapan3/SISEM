import logging
import time

from celery import shared_task
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone

from apps.medicos.models import MedicoImportJob
from apps.medicos.services import import_job_progress
from apps.medicos.services.medico_import_service import ImportFileError
from apps.medicos.uses_case.import_medicos import (
    ConfirmMedicosImportUseCase,
    MedicoImportRaceError,
)

logger = logging.getLogger(__name__)

# Throttle del avance: sin esto, 2700 filas = 2700 escrituras solo para la barra.
_PROGRESS_MIN_INTERVAL_S = 0.5


class _JobProgress:
    """
    Publica el avance SIEMPRE en la cache (visible aunque la fase SAVING
    corra dentro de la transacción del lote) y, fuera de una transacción,
    también en el job (queda persistido si la cache se pierde).
    """

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
        import_job_progress.set_progress(self.job_id, phase, done, total)
        if not connection.in_atomic_block:
            MedicoImportJob.objects.filter(id=self.job_id).update(
                phase=phase, processed=done, phase_total=total,
            )
        self._last_phase = phase
        self._last_write = now


def _finish(job_id, **fields):
    MedicoImportJob.objects.filter(id=job_id).update(
        fch_fin=timezone.now(), file_content=None, **fields,
    )
    import_job_progress.clear_progress(job_id)


@shared_task
def procesar_import_medicos(job_id):
    """
    Ejecuta un `MedicoImportJob` (encolado por `MedicoImportConfirmView`).
    Misma lógica todo-o-nada que el confirm síncrono: reusa
    `ConfirmMedicosImportUseCase` tal cual, solo le agrega reporte de avance.

    Sin reintentos automáticos (igual que el import de usuarios): si el
    worker muere a mitad, la transacción del lote se revierte y el job queda
    RUNNING hasta que vence la ventana de job activo; se vuelve a subir el
    archivo.
    """
    # Toma atómica del job: solo PENDING -> RUNNING, para que una entrega
    # duplicada del broker no procese el mismo archivo dos veces.
    claimed = MedicoImportJob.objects.filter(
        id=job_id, status=MedicoImportJob.Status.PENDING,
    ).update(status=MedicoImportJob.Status.RUNNING, fch_inicio=timezone.now())
    if not claimed:
        logger.warning("MedicoImportJob %s no esta PENDING; se ignora", job_id)
        return

    job = MedicoImportJob.objects.select_related("actor").get(id=job_id)
    file = SimpleUploadedFile(job.file_name, bytes(job.file_content))

    try:
        result = ConfirmMedicosImportUseCase().execute(
            file, job.actor, progress=_JobProgress(job_id),
        )
    except ImportFileError as exc:
        _finish(
            job_id,
            status=MedicoImportJob.Status.ERROR,
            phase=MedicoImportJob.Phase.DONE,
            error_code=exc.code,
            error_message=exc.message,
        )
        return
    except MedicoImportRaceError as exc:
        _finish(
            job_id,
            status=MedicoImportJob.Status.ERROR,
            phase=MedicoImportJob.Phase.DONE,
            error_code="MEDICO_IMPORT_RACE",
            error_message=(
                "No se pudo completar el import: el usuario de la fila "
                f"{exc.row_number} ({exc.usuario}) ya no existe o cambió "
                "de estado. No se creó ningún médico."
            ),
        )
        return
    except Exception:
        logger.exception("MedicoImportJob %s fallo inesperadamente", job_id)
        _finish(
            job_id,
            status=MedicoImportJob.Status.ERROR,
            phase=MedicoImportJob.Phase.DONE,
            error_code="IMPORT_UNEXPECTED_ERROR",
            error_message="Error inesperado al importar. No se creó ningún médico.",
        )
        return

    has_errors = result.pop("has_errors", False)
    job.set_result(result)
    _finish(
        job_id,
        status=(
            MedicoImportJob.Status.VALIDATION_FAILED if has_errors else MedicoImportJob.Status.SUCCESS
        ),
        phase=MedicoImportJob.Phase.DONE,
        total_records=result["totalRecords"],
        inserted=result["inserted"],
        result_json=job.result_json,
    )
    logger.info(
        "MedicoImportJob %s terminado: filas=%s insertados=%s errores=%s warnings=%s",
        job_id,
        result["totalRecords"],
        result["inserted"],
        result["totalErrores"],
        result["totalWarnings"],
    )
