from datetime import date

from django.db import transaction

from apps.medicos.repositories.centro_repository import CentroRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.services.errors import VisitDomainError


@transaction.atomic
def add_centro(user_id, data, *, actor_id, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    centro = CentroRepository.get_catalogo(data.get("centroId"))
    if not centro:
        raise VisitDomainError("CENTRO_NOT_FOUND", "Centro no encontrado.", 404)

    return CentroRepository.create(
        medico=medico,
        centro=centro,
        tipo_adscripcion=data.get("tipoAdscripcion", "DEFINITIVA"),
        fecha_inicio=data.get("fechaInicio", date.today()),
        fecha_fin=data.get("fechaFin") or None,
        created_by_id=actor_id,
    )


def remove_centro(user_id, rel_id, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    CentroRepository.deactivate(medico_id=medico.id, rel_id=rel_id)
