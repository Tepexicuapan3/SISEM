"""
Asistencia a una cita médica.

- El paciente tiene que hacer su check-in con anticipación: a más tardar
  ``citas.anticipacion_checkin_min`` minutos ANTES de la hora de la cita
  (30 por omisión, se cambia en cat_parametro). Si no llega a tiempo no se
  le da atención con esa cita y la cita queda en no_asistio.
- El check-in confirma la cita; al cerrar la consulta pasa a atendida.

El límite se compara por minuto: con cita a las 10:00 y 30 min, a las
9:30 todavía llega; a las 9:31 ya no.
"""
from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.recepcion.models import CitaMedica, EstatusCita, Visit
from apps.recepcion.services.errors import VisitDomainError

PARAM_ANTICIPACION = "citas.anticipacion_checkin_min"
ANTICIPACION_DEFAULT = 30

# Motivo tipificado del catálogo MotivoCita (migración catalogos/0021_motivos_cita).
MOTIVO_NO_ASISTIO_AUTOMATICO = "Paciente no se presentó"

ESTATUS_PENDIENTE = (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)


def anticipacion_checkin() -> timedelta:
    from apps.catalogos.services.parametro_service import get_param

    return timedelta(minutes=get_param(PARAM_ANTICIPACION, default=ANTICIPACION_DEFAULT))


def _minuto_actual():
    return timezone.now().replace(second=0, microsecond=0)


def limite_checkin(fecha_hora):
    return fecha_hora - anticipacion_checkin()


def limite_vencido(fecha_hora) -> bool:
    return _minuto_actual() > limite_checkin(fecha_hora)


def exigir_checkin_a_tiempo(cita: CitaMedica) -> None:
    if limite_vencido(cita.fecha_hora):
        minutos = int(anticipacion_checkin().total_seconds() // 60)
        raise VisitDomainError(
            "CITA_FUERA_DE_TIEMPO",
            f"El paciente debía presentarse a más tardar a las "
            f"{timezone.localtime(limite_checkin(cita.fecha_hora)):%H:%M} ({minutos} min antes de su cita "
            f"de las {timezone.localtime(cita.fecha_hora):%H:%M}). No se le puede dar atención con esta cita.",
            409,
        )


def citas_vencidas_sin_checkin():
    """Citas pendientes cuyo límite de check-in ya pasó y que no tienen ficha."""
    con_ficha = Visit.objects.filter(appointment_id=OuterRef("folio"))
    return CitaMedica.objects.filter(
        estatus__in=ESTATUS_PENDIENTE,
        verificado_en__isnull=True,
        fecha_hora__lt=_minuto_actual() + anticipacion_checkin(),
    ).exclude(Exists(con_ficha))


def confirmar_por_checkin(appointment_id: str | None, changed_by_id: int | None) -> None:
    """La ficha de una cita la deja confirmada (la máquina de estados registra la bitácora)."""
    from apps.recepcion.repositories.citas_repository import CitasRepository

    cita = _cita_pendiente(appointment_id)
    if cita is not None and cita.estatus == EstatusCita.AGENDADA:
        CitasRepository.update_estatus(cita, EstatusCita.CONFIRMADA, changed_by_id=changed_by_id)


def marcar_atendida(appointment_id: str | None, changed_by_id: int | None) -> None:
    """Al cerrar la consulta de una ficha con cita, la cita queda atendida."""
    from apps.recepcion.repositories.citas_repository import CitasRepository

    cita = _cita_pendiente(appointment_id)
    if cita is not None:
        CitasRepository.update_estatus(cita, EstatusCita.ATENDIDA, changed_by_id=changed_by_id)


def cita_de_ficha(appointment_id: str | None) -> CitaMedica | None:
    if not appointment_id:
        return None
    return CitaMedica.objects.filter(folio=appointment_id).first()


def _cita_pendiente(appointment_id: str | None) -> CitaMedica | None:
    if not appointment_id:
        return None
    return CitaMedica.objects.filter(folio=appointment_id, estatus__in=ESTATUS_PENDIENTE).first()
