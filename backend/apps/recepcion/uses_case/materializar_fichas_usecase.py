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

No asistió (``marcar_fichas_no_llegaron``): la ficha que sigue "Por llegar"
pasada la hora de la cita más ``citas.tolerancia_no_show_min`` (60 min por
omisión) pasa a no_show y su cita a no_asistio. Si no, se quedaría en la
bandeja y bloquearía las fichas siguientes del paciente. Cubre también las de
días anteriores (por ejemplo, si la tarea no corrió).
"""

import logging
import uuid
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.consulta_medica.services.paciente_entrada import llave_publica
from apps.medicos.identity import usuario_id_for_medico
from apps.catalogos.models import MotivoCita
from apps.realtime.events import publish_visit_created, publish_visit_no_show
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.asistencia_cita_service import ESTATUS_PENDIENTE, MOTIVO_NO_ASISTIO_AUTOMATICO
from apps.recepcion.models import CitaMedica, EstatusCita, OrigenCanalCita, Visit
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.qr_checkin_usecase import _resolver_paciente
from apps.recepcion.uses_case.visit_queue_usecase import NOTA_FICHA_AUTOMATICA, change_visit_status, create_visit

logger = logging.getLogger(__name__)

__all__ = [
    "NOTA_FICHA_AUTOMATICA",
    "genera_ficha_automatica",
    "marcar_fichas_no_llegaron",
    "materializar_ficha",
    "materializar_fichas_del_dia",
]

PARAM_TOLERANCIA = "citas.tolerancia_no_show_min"
TOLERANCIA_DEFAULT = 60

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
        visit = create_visit(
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
        # La bandeja se actualiza por tiempo real; solo si la ficha quedó guardada.
        transaction.on_commit(lambda: _avisar_bandeja(visit))
    return visit


def _avisar_bandeja(visit: dict) -> None:
    request_id = str(uuid.uuid4())
    try:
        publish_visit_created(
            visit_id=visit["id"], status=visit["status"], request_id=request_id, correlation_id=request_id,
        )
    except Exception:
        logger.exception("No se pudo publicar la ficha automática %s en tiempo real", visit["id"])


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


def tolerancia_no_show() -> timedelta:
    from apps.catalogos.services.parametro_service import get_param

    return timedelta(minutes=get_param(PARAM_TOLERANCIA, default=TOLERANCIA_DEFAULT))


def _hora_de_la_cita(visit: Visit):
    return timezone.make_aware(datetime.combine(visit.fecha_consulta, visit.hora_consulta))


def _fichas_por_llegar(hasta_fecha):
    return Visit.objects.filter(
        origen_ficha=Visit.OrigenFicha.AUTOMATICA,
        llegada_en__isnull=True,
        status="en_espera",
        fecha_consulta__lte=hasta_fecha,
        hora_consulta__isnull=False,
    ).order_by("fecha_consulta", "hora_consulta")


def _marcar_no_llego(visit: Visit, motivo, minutos: int) -> None:
    with transaction.atomic():
        contrato = change_visit_status(visit.id_visit, "no_show", changed_by_id=None)
        cita = CitaMedica.objects.filter(folio=visit.appointment_id, estatus__in=ESTATUS_PENDIENTE).first()
        if cita is not None:
            CitasRepository.update_estatus(
                cita,
                EstatusCita.NO_ASISTIO,
                motivo_cancelacion=motivo,
                motivo_detalle=f"Automático: no llegó {minutos} min después de la hora de la cita.",
                changed_by_id=None,
            )
        transaction.on_commit(lambda: _avisar_no_show(contrato))


def _avisar_no_show(visit: dict) -> None:
    request_id = str(uuid.uuid4())
    try:
        publish_visit_no_show(
            visit_id=visit["id"], status=visit["status"], previous_status="en_espera",
            request_id=request_id, correlation_id=request_id,
        )
    except Exception:
        logger.exception("No se pudo publicar el no asistió de la ficha %s en tiempo real", visit["id"])


def marcar_fichas_no_llegaron(ahora=None) -> dict:
    """Fichas automáticas que siguen "Por llegar" pasada la tolerancia: no asistió."""
    ahora = ahora or timezone.now()
    tolerancia = tolerancia_no_show()
    minutos = int(tolerancia.total_seconds() // 60)
    motivo = MotivoCita.objects.filter(name=MOTIVO_NO_ASISTIO_AUTOMATICO, is_active=True).first()
    marcadas = 0
    errores = 0
    for visit in _fichas_por_llegar(timezone.localtime(ahora).date()):
        if _hora_de_la_cita(visit) + tolerancia >= ahora:
            continue
        try:
            _marcar_no_llego(visit, motivo, minutos)
            marcadas += 1
        except Exception:
            errores += 1
            logger.exception("Error marcando no asistió la ficha automática %s", visit.folio)
    if marcadas or errores:
        logger.info("Fichas automáticas sin llegada: marcadas=%s errores=%s", marcadas, errores)
    return {"marcadas": marcadas, "errores": errores}
