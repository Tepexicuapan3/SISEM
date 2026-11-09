"""
Cita de seguimiento desde la nota (P-12 del legado, ``parte_familiar.jsp`` ->
``horario_fam.jsp``).

Decisión 2026-10-14: el médico elige un horario libre de SU agenda en el
diálogo de la consulta y la cita se crea al cerrar la nota, en la misma
transacción. SIRES no tiene "médico familiar" asignado (P-03), así que
siempre es con el médico que atiende. Sin horario elegido la fecha queda
como indicación y la cita la agenda recepción (comportamiento anterior).

La cita pasa por ``CitasRepository.create``: mismas reglas que recepción
(horario futuro, ausencias, topes por día, horario no exclusivo del portal).
"""

from datetime import datetime

from django.db.models import Count, Q
from django.utils import timezone

from apps.medicos.models import CatMedico
from apps.recepcion.models import CitaMedica, HorarioDisponible
from apps.recepcion.repositories.citas_repository import CitasRepository, q_slots_futuros
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import llave_publica

MOTIVO_SEGUIMIENTO = "Cita de seguimiento"


def _medico_del_usuario(doctor_id):
    return CatMedico.objects.filter(id_usuario_id=doctor_id).first()


# Libre = sin cita y sin bloqueo (ausencia, tope, etc.).
Q_LIBRE = Q(disponible=True, cita__isnull=True)


def _slots_agenda(medico):
    """Horarios futuros del médico que se pueden mostrar (libres u ocupados)."""
    return (
        HorarioDisponible.objects
        .filter(medico=medico)
        .exclude(canal="LINEA")  # exclusivos del portal
        .filter(q_slots_futuros())
    )


def _slots_libres(medico):
    return _slots_agenda(medico).filter(Q_LIBRE)


def list_follow_up_days(desde, hasta, doctor_id) -> list[dict]:
    """Días con agenda del médico que atiende, con cuántos horarios quedan
    libres de cuántos hay (``libres == 0``: día lleno)."""
    medico = _medico_del_usuario(doctor_id)
    if medico is None:
        return []
    dias = (
        _slots_agenda(medico)
        .filter(fecha__gte=desde, fecha__lte=hasta)
        .values("fecha")
        .annotate(libres=Count("id", filter=Q_LIBRE), total=Count("id"))
        .order_by("fecha")
    )
    return [
        {"fecha": d["fecha"].isoformat(), "libres": d["libres"], "total": d["total"]}
        for d in dias
    ]


def doctor_has_agenda(doctor_id) -> bool:
    """Si el usuario es médico con horarios generados de aquí en adelante
    (libres u ocupados). Sin agenda no hay horarios que ofrecer."""
    medico = _medico_del_usuario(doctor_id)
    if medico is None:
        return False
    return HorarioDisponible.objects.filter(medico=medico).filter(q_slots_futuros()).exists()


def next_follow_up_day(desde, doctor_id):
    """Primer día desde ``desde`` (incluido) con horarios libres, o None."""
    medico = _medico_del_usuario(doctor_id)
    if medico is None:
        return None
    return (
        _slots_libres(medico)
        .filter(fecha__gte=desde)
        .order_by("fecha")
        .values_list("fecha", flat=True)
        .first()
    )


def list_follow_up_slots(fecha, doctor_id) -> list[dict]:
    """Horarios del médico que atiende para la fecha de seguimiento, libres y
    ocupados (``disponible``), para que el médico vea cómo está su día."""
    medico = _medico_del_usuario(doctor_id)
    if medico is None:
        return []
    slots = (
        _slots_agenda(medico)
        .filter(fecha=fecha)
        .select_related("consultorio")
        .order_by("hora")
    )
    return [
        {
            "slotId": s.id,
            "hora": s.hora.strftime("%H:%M"),
            "duracionMin": s.duracion_min,
            "consultorioNombre": s.consultorio.name if s.consultorio_id else None,
            "disponible": s.disponible and s.cita_id is None,
        }
        for s in slots
    ]


def _invalido(mensaje):
    return VisitDomainError(
        "VALIDATION_ERROR", "Hay errores en el formulario", 422,
        details={"followUpSlotId": [mensaje]},
    )


def schedule_follow_up(visit, follow_up_date, slot_id, doctor_id) -> CitaMedica:
    """
    Crea la cita de seguimiento. Se llama dentro de la transacción del
    cierre: si falla, la nota no se cierra y el médico elige otro horario.
    """
    if not follow_up_date:
        raise _invalido("Indica la fecha de seguimiento antes de elegir el horario.")
    if not llave_publica(visit)[0]:
        raise _invalido("La visita no tiene expediente; la cita la agenda recepción.")

    slot = HorarioDisponible.objects.select_related("medico").filter(pk=slot_id).first()
    if slot is None or slot.fecha != follow_up_date:
        raise _invalido("El horario elegido no corresponde a la fecha de seguimiento.")
    if slot.medico.id_usuario_id != doctor_id:
        raise _invalido("Solo puedes agendar el seguimiento en tu propia agenda.")

    fecha_hora = timezone.make_aware(datetime.combine(slot.fecha, slot.hora))
    try:
        cita = CitasRepository.create(
            no_exp=llave_publica(visit)[0],
            pk_num=llave_publica(visit)[1],
            medico_id=slot.medico_id,
            fecha_hora=fecha_hora,
            servicio_tipo=visit.service_type,
            consultorio_id=slot.consultorio_id,
            duracion_min=slot.duracion_min,
            motivo=MOTIVO_SEGUIMIENTO,
            notas=f"Consulta {visit.folio}",
            created_by_id=doctor_id,
        )
    except ValueError as exc:
        # Ocupado, ausencia, tope por día, etc.: el médico elige otro.
        raise VisitDomainError("FOLLOW_UP_SLOT_UNAVAILABLE", str(exc), 409) from exc
    return CitaMedica.objects.get(pk=cita["id"])


def follow_up_contract(cita: CitaMedica | None) -> dict | None:
    if cita is None:
        return None
    return {"folio": cita.folio, "fechaHora": cita.fecha_hora.isoformat()}
