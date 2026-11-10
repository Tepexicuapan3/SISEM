"""
Fichas automáticas de las citas (decisión 2026-11-10).

Las citas que no son del portal (las agenda recepción o el médico al cerrar
la consulta) no hacen check-in: el día de la cita generan su ficha en espera
para que aparezcan en la bandeja de recepción. El check-in (QR o folio) queda
solo para las citas del portal en línea.

La ficha no se crea al agendar porque aparecería en la bandeja ese mismo día
y bloquearía otras visitas del paciente hasta la fecha de la cita
(``exists_open_visit_for_patient``). Se crea:

- con la tarea ``recepcion.tasks.materializar_fichas`` (cada 5 minutos de
  5:00 a 23:55; reintenta las que no se pudieron crear);
- en el momento, si la cita se agenda para hoy (``agendar_cita``);
- con el comando ``manage.py materializar_fichas`` (desarrollo, sin Celery).

Se puede correr las veces que haga falta: una cita con ficha no se vuelve a
tomar. Con un paciente sin vigencia o con otra visita abierta la ficha no se
crea y la cita queda en el resumen con su motivo.
"""

import logging

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.consulta_medica.services.paciente_entrada import llave_publica
from apps.medicos.identity import usuario_id_for_medico
from apps.recepcion.models import CitaMedica, EstatusCita, OrigenCanalCita, Visit
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.qr_checkin_usecase import _resolver_paciente
from apps.recepcion.uses_case.visit_queue_usecase import NOTA_FICHA_AUTOMATICA, create_visit

logger = logging.getLogger(__name__)

__all__ = ["NOTA_FICHA_AUTOMATICA", "genera_ficha_automatica", "materializar_ficha", "materializar_fichas_del_dia"]

ESTATUS_CON_FICHA = (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)


def genera_ficha_automatica(cita: CitaMedica) -> bool:
    """Las del portal hacen check-in; las demás generan su ficha."""
    return cita.origen_canal != OrigenCanalCita.PORTAL


def _citas_sin_ficha(fecha):
    con_ficha = Visit.objects.filter(appointment_id=OuterRef("folio"))
    return (
        CitaMedica.objects
        .filter(fecha_hora__date=fecha, estatus__in=ESTATUS_CON_FICHA)
        .exclude(origen_canal=OrigenCanalCita.PORTAL)
        .exclude(Exists(con_ficha))
        .order_by("fecha_hora")
    )


def materializar_ficha(cita: CitaMedica) -> dict:
    """
    Crea la ficha en espera de la cita. Lanza VisitDomainError si no se puede
    (``PATIENT_NO_SERVICE``, ``VISIT_DUPLICATE_SUBMIT``, ...).
    """
    no_exp, pk_num = llave_publica(cita)
    nombre, vigente = _resolver_paciente(no_exp, pk_num)
    if not vigente:
        # Sin vigencia se atiende solo con autorización de Capital Humano:
        # lo resuelve recepción al llegar el paciente.
        raise VisitDomainError("PATIENT_NO_SERVICE", "El paciente no tiene vigencia activa.", 409)
    local = timezone.localtime(cita.fecha_hora)
    # Savepoint: si la ficha se rechaza, la transacción de quien llama sigue.
    with transaction.atomic():
        return create_visit(
            no_exp=no_exp,
            pk_num=pk_num,
            nombre_paciente=nombre or None,
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            service_type=cita.servicio_tipo,
            appointment_id=cita.folio,
            doctor_id=usuario_id_for_medico(cita.medico_id),
            medico_id=cita.medico_id,
            consultorio_id=cita.consultorio_id,
            notes=cita.motivo,
            fecha_consulta=local.date(),
            hora_consulta=local.time(),
            automatica=True,
        )


def materializar_fichas_del_dia(fecha=None) -> dict:
    """Crea las fichas de las citas de ``fecha`` (hoy) que todavía no tienen."""
    fecha = fecha or timezone.localdate()
    creadas = 0
    omitidas = []
    for cita in _citas_sin_ficha(fecha):
        try:
            materializar_ficha(cita)
            creadas += 1
        except VisitDomainError as exc:
            omitidas.append({"folio": cita.folio, "motivo": exc.code})
        except Exception:
            logger.exception("Error creando la ficha automática de la cita %s", cita.folio)
            omitidas.append({"folio": cita.folio, "motivo": "ERROR"})
    if omitidas:
        logger.info("Fichas automáticas %s: creadas=%s omitidas=%s", fecha, creadas, omitidas)
    return {"fecha": fecha.isoformat(), "creadas": creadas, "omitidas": omitidas}
