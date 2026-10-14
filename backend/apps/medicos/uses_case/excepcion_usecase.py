from typing import NamedTuple

from django.db import transaction

from apps.medicos.repositories.excepcion_repository import ExcepcionRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.services.bloqueo_slots_service import (
    bloquear_slots_por_excepcion,
    citas_afectadas_por_excepcion,
    desbloquear_slots_de_excepcion,
)
from apps.recepcion.services.errors import VisitDomainError


class ExcepcionCreada(NamedTuple):
    excepcion: object
    # Citas ya agendadas dentro de la ausencia: NO se cancelan, recepción
    # las reprograma.
    citas_afectadas: list
    horarios_bloqueados: int


def list_excepciones(medico_id, *, request=None):
    medico = MedicoRepository.resolve(medico_id, request=request)
    return ExcepcionRepository.list_active(getattr(medico, "id", None))


@transaction.atomic
def create_excepcion(medico_id, data, *, actor_id, request=None):
    medico = MedicoRepository.resolve(medico_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    exc = ExcepcionRepository.create(
        medico=medico,
        tipo=data.get("tipo"),
        fecha_inicio=data.get("fechaInicio"),
        fecha_fin=data.get("fechaFin"),
        hora_inicio=data.get("horaInicio") or None,
        hora_fin=data.get("horaFin") or None,
        consultorio_id=data.get("consultorioId") or None,
        motivo=data.get("motivo") or None,
        created_by_id=actor_id,
    )
    # El estatus del médico ya NO se toca: antes, unas vacaciones futuras lo
    # dejaban no disponible desde hoy y borrar la ausencia nunca lo
    # restauraba. La disponibilidad sale de las fechas de cada ausencia; el
    # estatus queda como decisión manual del administrador.
    # ExcepcionRepository.create no recarga: las horas llegan como texto.
    exc.refresh_from_db()

    horarios_bloqueados = bloquear_slots_por_excepcion(exc)
    return ExcepcionCreada(exc, citas_afectadas_por_excepcion(exc), horarios_bloqueados)


@transaction.atomic
def delete_excepcion(medico_id, exc_id, *, request=None):
    medico = MedicoRepository.resolve(medico_id, request=request)
    medico_pk = getattr(medico, "id", None)
    exc = ExcepcionRepository.get(medico_id=medico_pk, exc_id=exc_id)
    ExcepcionRepository.deactivate(medico_id=medico_pk, exc_id=exc_id)
    if exc is not None:
        # Rehabilita los horarios que bloqueó (salvo los que otra ausencia
        # activa siga cubriendo).
        desbloquear_slots_de_excepcion(exc)
