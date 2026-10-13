"""
Avance en vivo de un `MedicoImportJob`, guardado en la cache (Redis).

La fase SAVING corre dentro de la transacción atómica del lote: un UPDATE al
job desde ahí no sería visible para el polling hasta el commit (y se
revertiría con el lote). La cache no participa de la transacción y la
comparten `backend` (vista de estado) y `celery-worker` (tarea).
"""

from django.core.cache import cache

# Holgado respecto a la duración de un import; se borra al terminar el job.
_TTL_S = 6 * 60 * 60


def _key(job_id) -> str:
    return f"medico_import_job:{job_id}:progress"


def set_progress(job_id, phase: str, done: int, total: int) -> None:
    cache.set(_key(job_id), {"phase": phase, "processed": done, "phaseTotal": total}, _TTL_S)


def get_progress(job_id):
    """`{"phase", "processed", "phaseTotal"}` o None si no hay avance publicado."""
    return cache.get(_key(job_id))


def clear_progress(job_id) -> None:
    cache.delete(_key(job_id))
