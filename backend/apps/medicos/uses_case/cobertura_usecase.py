from django.db import transaction
from rest_framework import serializers as drf_serializers

from apps.medicos.repositories.cobertura_repository import CoberturaRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.medicos.serializers import CoberturaHorarioSerializer, validate_horarios
from apps.recepcion.services.errors import VisitDomainError


def _validar_horarios(horarios_payload: list) -> list:
    try:
        return validate_horarios(horarios_payload, serializer_class=CoberturaHorarioSerializer)
    except drf_serializers.ValidationError as exc:
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en los horarios.", 400, details=exc.detail,
        ) from exc


def list_coberturas(medico_id, *, request=None):
    """
    Coberturas donde el médico participa como suplente o como titular
    (ambos roles). `medico_id` es obligatorio -- ver validación en la vista.
    """
    medico = MedicoRepository.resolve(medico_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    return CoberturaRepository.list_for_medico(medico)


@transaction.atomic
def create_cobertura(data, *, actor_id, request=None):
    suplente = MedicoRepository.resolve(data.get("medicoSuplenteId"), request=request)
    titular = MedicoRepository.resolve(data.get("medicoTitularId"), request=request)
    if not suplente or not titular:
        raise VisitDomainError(
            "MEDICO_NOT_FOUND", "Médico suplente o titular no encontrado.", 404,
        )

    cob = CoberturaRepository.create(
        suplente=suplente,
        titular=titular,
        consultorio_id=data.get("consultorioId"),
        centro_id=data.get("centroId"),
        fecha_inicio=data.get("fechaInicio"),
        fecha_fin=data.get("fechaFin"),
        motivo=data.get("motivo", "OTRO"),
        created_by_id=actor_id,
    )
    CoberturaRepository.create_horarios(cob, _validar_horarios(data.get("horarios", [])))

    return CoberturaRepository.get_with_horarios(cob.id)


def delete_cobertura(cobertura_id):
    cobertura = CoberturaRepository.get_by_id(cobertura_id)
    if not cobertura:
        raise VisitDomainError("NOT_FOUND", "Cobertura no encontrada.", 404)

    CoberturaRepository.cancel(cobertura)
