from apps.medicos.repositories.especialidad_repository import EspecialidadRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.services.errors import VisitDomainError


def add_especialidad(user_id, data, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    esp_id = data.get("especialidadId")
    if not esp_id:
        raise VisitDomainError("VALIDATION_ERROR", "especialidadId requerido.", 400)

    especialidad = EspecialidadRepository.get_catalogo(esp_id)
    if not especialidad:
        raise VisitDomainError("ESPECIALIDAD_NOT_FOUND", "Especialidad no encontrada.", 404)

    es_principal = bool(data.get("esPrincipal", False))
    if es_principal:
        EspecialidadRepository.unset_principal(medico)

    rel, created = EspecialidadRepository.upsert(
        medico=medico, especialidad=especialidad, es_principal=es_principal,
    )
    return rel, created


def remove_especialidad(user_id, especialidad_id, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    EspecialidadRepository.delete(medico_id=medico.id, especialidad_id=especialidad_id)
