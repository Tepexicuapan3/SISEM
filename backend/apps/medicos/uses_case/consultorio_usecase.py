from datetime import date

from django.db import transaction
from rest_framework import serializers as drf_serializers

from apps.medicos.repositories.consultorio_repository import ConsultorioRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.medicos.serializers import validate_horarios
from apps.recepcion.services.errors import VisitDomainError


def _validar_horarios(horarios_payload: list) -> list:
    """Valida forma/tipo de cada horario (día, horas, canal) -- ver
    apps.medicos.serializers. Devuelve la lista normalizada o lanza
    VisitDomainError con el detalle campo por campo."""
    try:
        return validate_horarios(horarios_payload)
    except drf_serializers.ValidationError as exc:
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en los horarios.", 400, details=exc.detail,
        ) from exc


@transaction.atomic
def add_consultorio(user_id, data, *, actor_id, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)

    consultorio = ConsultorioRepository.get_catalogo(data.get("consultorioId"))
    if not consultorio:
        raise VisitDomainError("CONSULTORIO_NOT_FOUND", "Consultorio no encontrado.", 404)

    horarios_payload = _validar_horarios(data.get("horarios", []))

    rmc = ConsultorioRepository.create(
        medico=medico,
        consultorio=consultorio,
        tipo_asignacion=data.get("tipoAsignacion", "PERMANENTE"),
        fecha_inicio=data.get("fechaInicio", date.today()),
        fecha_fin=data.get("fechaFin") or None,
        created_by_id=actor_id,
    )
    ConsultorioRepository.create_horarios(rmc, horarios_payload)

    return ConsultorioRepository.get_with_horarios(rmc.id)


def update_consultorio_asignacion(user_id, rmc_id, data, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    rmc = ConsultorioRepository.get_asignacion(rmc_id=rmc_id, medico_id=getattr(medico, "id", None))
    if not rmc:
        raise VisitDomainError("NOT_FOUND", "Asignación no encontrada.", 404)

    consultorio = None
    if "consultorioId" in data:
        consultorio = ConsultorioRepository.get_catalogo(data["consultorioId"])
        if not consultorio:
            raise VisitDomainError("CONSULTORIO_NOT_FOUND", "Consultorio no encontrado.", 404)

    ConsultorioRepository.update(
        rmc,
        consultorio=consultorio,
        tipo_asignacion=data.get("tipoAsignacion"),
    )
    return ConsultorioRepository.get_with_horarios(rmc.id)


def remove_consultorio(user_id, rmc_id, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    ConsultorioRepository.deactivate(medico_id=getattr(medico, "id", None), rmc_id=rmc_id)


@transaction.atomic
def save_horario(user_id, rmc_id, data, *, request=None):
    medico = MedicoRepository.resolve(user_id, request=request)
    rmc = ConsultorioRepository.get_asignacion(rmc_id=rmc_id, medico_id=getattr(medico, "id", None))
    if not rmc:
        raise VisitDomainError("NOT_FOUND", "Asignación no encontrada.", 404)

    horarios_payload = _validar_horarios(data.get("horarios", []))

    ConsultorioRepository.replace_horarios(rmc, horarios_payload)
    _regenerar_slots(rmc.medico_id)

    return ConsultorioRepository.get_with_horarios(rmc.id)


def _regenerar_slots(medico_id):
    """
    Regenerar slots: elimina futuros disponibles y vuelve a generar desde el
    nuevo horario. Los slots con cita asignada se preservan. Cruza a
    `recepcion` (dueño de HorarioDisponible/CitasRepository) -- orquestación
    explícita a nivel de uses_case, no oculta en el repositorio de medicos.
    """
    from apps.recepcion.models import HorarioDisponible
    from apps.recepcion.repositories.citas_repository import CitasRepository

    HorarioDisponible.objects.filter(
        medico_id=medico_id,
        fecha__gte=date.today(),
        disponible=True,
        cita__isnull=True,
    ).delete()
    CitasRepository.generar_slots_medico(medico_id=medico_id, dias_adelante=60)
