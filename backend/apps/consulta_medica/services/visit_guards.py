"""Guards de estado de visita para creadores de hijos de la nota.

Change cancelacion-nota-cascada: una nota cancelada (Visit.status == "cancelada")
no admite diagnosticos, recetas, pases, resultados ni incapacidades nuevos.
`lock_visit_not_cancelled` toma el lock de la fila Visit (mismo primer lock que
`cancel_consultation`) para serializar con la cancelacion: o el hijo se crea
antes y la cascada lo ve, o la cancelacion gana y el creador recibe 409.
"""
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError

VISIT_CANCELLED_CODE = "VISIT_CANCELLED"


def _visit_cancelled_error():
    return VisitDomainError(
        VISIT_CANCELLED_CODE,
        "La nota de esta visita fue cancelada: no admite nuevos registros.",
        409,
    )


def ensure_visit_not_cancelled(visit):
    """Chequeo barato sin lock (409 VISIT_CANCELLED)."""
    if visit.status == "cancelada":
        raise _visit_cancelled_error()


def lock_visit_not_cancelled(visit_id):
    """Lock FOR UPDATE de la visita + recheck. Llamar DENTRO de transaction.atomic()."""
    locked = VisitRepository.get_for_update(visit_id)
    if locked is None:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    ensure_visit_not_cancelled(locked)
    return locked
