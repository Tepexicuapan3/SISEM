from django.db import transaction
from django.utils import timezone

from apps.medicos.repositories.excepcion_repository import ExcepcionRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.services.errors import VisitDomainError

# Tipos de excepción que, al registrarse, reflejan también el estatus del
# médico (ausencia de larga duración) -- ver create_excepcion.
_TIPOS_QUE_ACTUALIZAN_ESTATUS = ("VACACIONES", "INCAPACIDAD", "SUSPENSION")


def list_excepciones(user_id, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    return ExcepcionRepository.list_active(getattr(medico, "id", None))


@transaction.atomic
def create_excepcion(user_id, data, *, actor_id, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
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

    # Actualizar estatus si es una excepción de baja/vacaciones de larga duración
    if exc.tipo in _TIPOS_QUE_ACTUALIZAN_ESTATUS:
        medico.estatus_medico = exc.tipo if exc.tipo != "VACACIONES" else "VACACIONES"
        medico.updated_at = timezone.now()
        MedicoRepository.save(medico, update_fields=["estatus_medico", "updated_at"])

    return exc


def delete_excepcion(user_id, exc_id, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    ExcepcionRepository.deactivate(medico_id=getattr(medico, "id", None), exc_id=exc_id)
