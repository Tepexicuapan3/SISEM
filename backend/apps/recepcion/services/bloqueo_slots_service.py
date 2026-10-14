"""
Horarios bloqueados por ausencias del médico (``RelMedicoExcepcion``).

Cualquier ausencia (vacaciones, hora de comida, permiso, cambio de horario,
etc.) deja sin habilitar los horarios de su rango:

- Día completo (``hora_inicio`` null) o de ``hora_inicio`` a ``hora_fin``;
  un horario cuenta si se cruza con la ventana (inicio + duración).
- Si la ausencia tiene consultorio, solo afecta los horarios de ese
  consultorio.

Un horario bloqueado queda ``disponible=False`` con
``bloqueado_por_excepcion`` apuntando a la ausencia; así, al borrarla, se
rehabilitan solo los que ella bloqueó. Los horarios con cita no se tocan:
las citas afectadas se listan para que recepción las reprograme (no se
cancelan solas).

Todo lugar que crea o libera un horario pasa por acá para que una cita
cancelada no reabra un horario dentro de una ausencia.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.medicos.models import RelMedicoExcepcion
from apps.recepcion.models import CitaMedica, HorarioDisponible
from apps.recepcion.repositories.citas_repository import ESTATUS_CITA_ACTIVA, q_slots_futuros


def excepciones_activas(medico_id, desde, hasta, *, excluir_id=None) -> list[RelMedicoExcepcion]:
    qs = RelMedicoExcepcion.objects.filter(
        medico_id=medico_id,
        is_active=True,
        fecha_inicio__lte=hasta,
        fecha_fin__gte=desde,
    )
    if excluir_id is not None:
        qs = qs.exclude(pk=excluir_id)
    return list(qs.order_by("fecha_inicio", "id"))


def _cubre(exc, fecha, hora, duracion_min, consultorio_id) -> bool:
    if not (exc.fecha_inicio <= fecha <= exc.fecha_fin):
        return False
    if exc.consultorio_id is not None and exc.consultorio_id != consultorio_id:
        return False
    if exc.hora_inicio is None or exc.hora_fin is None:
        return True
    inicio = datetime.combine(fecha, hora)
    fin = inicio + timedelta(minutes=duracion_min or 0)
    return inicio < datetime.combine(fecha, exc.hora_fin) and fin > datetime.combine(fecha, exc.hora_inicio)


def excepcion_que_cubre(excepciones, fecha, hora, duracion_min, consultorio_id):
    """Primera ausencia de ``excepciones`` que cubre ese horario, o None."""
    return next(
        (e for e in excepciones if _cubre(e, fecha, hora, duracion_min, consultorio_id)),
        None,
    )


def excepcion_en_horario(medico_id, fecha, hora, duracion_min, consultorio_id):
    """Ausencia activa del médico que cubre ese horario (o None)."""
    return excepcion_que_cubre(
        excepciones_activas(medico_id, fecha, fecha), fecha, hora, duracion_min, consultorio_id,
    )


def _slots_en_rango(exc):
    return HorarioDisponible.objects.filter(
        medico_id=exc.medico_id,
        fecha__gte=exc.fecha_inicio,
        fecha__lte=exc.fecha_fin,
    ).filter(q_slots_futuros())


def slots_a_bloquear(exc) -> list[int]:
    """Ids de los horarios futuros y libres que cubre ``exc``."""
    return [
        s.id
        for s in _slots_en_rango(exc).filter(disponible=True, cita__isnull=True)
        if _cubre(exc, s.fecha, s.hora, s.duracion_min, s.consultorio_id)
    ]


@transaction.atomic
def bloquear_slots_por_excepcion(exc) -> int:
    """Bloquea los horarios libres que cubre ``exc``. Devuelve cuántos."""
    ids = slots_a_bloquear(exc)
    return HorarioDisponible.objects.filter(id__in=ids).update(
        disponible=False, bloqueado_por_excepcion=exc,
    )


def citas_afectadas_por_excepcion(exc) -> list[CitaMedica]:
    """Citas activas dentro de la ausencia; recepción las reprograma."""
    citas = (
        CitaMedica.objects
        .filter(
            medico_id=exc.medico_id,
            estatus__in=ESTATUS_CITA_ACTIVA,
            fecha_hora__gte=timezone.now(),
        )
        .select_related("consultorio")
        .order_by("fecha_hora")
    )
    afectadas = []
    for cita in citas:
        local = timezone.localtime(cita.fecha_hora)
        if _cubre(exc, local.date(), local.time(), cita.duracion_min, cita.consultorio_id):
            afectadas.append(cita)
    return afectadas


def liberar_slots(slots) -> None:
    """
    Libera horarios (cita cancelada, no asistió, ficha cancelada, ausencia
    borrada). Si otra ausencia activa los cubre, quedan bloqueados por ella
    en vez de volver a estar disponibles.
    """
    for slot in slots:
        exc = excepcion_en_horario(
            slot.medico_id, slot.fecha, slot.hora, slot.duracion_min, slot.consultorio_id,
        )
        HorarioDisponible.objects.filter(pk=slot.pk).update(
            disponible=exc is None,
            bloqueado_por_excepcion=exc,
            cita=None,
        )


@transaction.atomic
def desbloquear_slots_de_excepcion(exc) -> None:
    """Al borrar ``exc`` (ya inactiva) se rehabilitan los horarios que bloqueó."""
    liberar_slots(
        HorarioDisponible.objects.select_for_update().filter(
            bloqueado_por_excepcion=exc, cita__isnull=True,
        )
    )
