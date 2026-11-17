"""
Cita de seguimiento de una nota cancelada (K1 de P-12).

Cuando se cancela una nota, su cita de seguimiento ya no tiene razón de ser:
ocupa un horario y el paciente llegaría a una cita de una consulta anulada.
La cascada de cancelación (``note_cancellation_usecase``) la cancela en su
misma transacción con lo que expone este módulo.

La cita se liga a la nota por la convención de siempre: motivo
``MOTIVO_CITA_SEGUIMIENTO`` y notas "Consulta <folio de la visita>". Solo se
cancela si está vigente y no tiene ficha (D4): con ficha el paciente ya está
en la unidad y la cita se deja para que recepción decida.
"""

from django.db.models import Exists, OuterRef

from apps.catalogos.models import MotivoCita
from apps.recepcion.models import (
    MOTIVO_CITA_SEGUIMIENTO,
    CanalMovimiento,
    CitaEstatusLog,
    CitaMedica,
    EstatusCita,
    Visit,
)
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.uses_case.agendar_cita_usecase import notas_de_cita_de_seguimiento

# Motivo tipificado sembrado por la migración 0040 de recepción.
MOTIVO_NOTA_CANCELADA = "Consulta cancelada"

_ESTATUS_VIGENTES = (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)


def _citas_vigentes_de_la_nota(visit_folio: str):
    return CitaMedica.objects.filter(
        motivo=MOTIVO_CITA_SEGUIMIENTO,
        notas=notas_de_cita_de_seguimiento(visit_folio),
        estatus__in=_ESTATUS_VIGENTES,
    ).order_by("pk")


def _q_con_ficha():
    return Exists(Visit.objects.filter(appointment_id=OuterRef("folio")))


def citas_de_seguimiento_a_cancelar(visit_folio: str, *, lock: bool = False) -> list[CitaMedica]:
    """Citas de seguimiento vigentes y sin ficha de la nota. Con ``lock`` las
    bloquea (debe llamarse dentro de ``transaction.atomic()``)."""
    qs = _citas_vigentes_de_la_nota(visit_folio).exclude(_q_con_ficha())
    if lock:
        qs = qs.select_for_update()
    return list(qs)


def citas_de_seguimiento_con_ficha(visit_folio: str) -> list[CitaMedica]:
    """Citas de seguimiento vigentes de la nota que ya tienen ficha: se dejan."""
    return list(_citas_vigentes_de_la_nota(visit_folio).filter(_q_con_ficha()))


def avisar_cita_con_ficha(cita: CitaMedica, *, cancellation_id: int, changed_by_id: int) -> None:
    """D4: la cita se deja (el paciente ya está en la unidad) y queda el aviso
    en su bitácora, sin cambio de estatus, para que recepción decida."""
    CitaEstatusLog.objects.create(
        cita=cita,
        from_status=cita.estatus,
        to_status=cita.estatus,
        changed_by_id=changed_by_id,
        notes=f"Nota cancelada #{cancellation_id}; la cita ya tiene ficha y no se canceló.",
        canal=CanalMovimiento.SISTEMA,
    )


def cancelar_cita_de_nota_cancelada(cita: CitaMedica, *, cancellation_id: int, changed_by_id: int) -> None:
    """Cancela la cita por la nota cancelada: libera el horario y deja el
    movimiento en la bitácora de la cita (canal SISTEMA)."""
    motivo = MotivoCita.objects.filter(name=MOTIVO_NOTA_CANCELADA, is_active=True).first()
    CitasRepository.update_estatus(
        cita,
        EstatusCita.CANCELADA,
        motivo_cancelacion=motivo,
        motivo_detalle=f"Nota cancelada #{cancellation_id}",
        changed_by_id=changed_by_id,
        canal=CanalMovimiento.SISTEMA,
    )
