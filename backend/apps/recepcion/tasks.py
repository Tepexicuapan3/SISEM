"""
apps/recepcion/tasks.py
=======================
Tareas Celery del módulo Citas Médicas.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.catalogos.models import MotivoCita
from apps.medicos.models import CatMedico
from .models import CitaMedica, EstatusCita
from .repositories.citas_repository import CitasRepository
from .services.notificacion_service import NotificacionCitaService

logger = logging.getLogger(__name__)

# Motivo tipificado (catálogo MotivoCita, ver migración
# catalogos/0021_motivos_cita) usado por el marcado automático de
# no_asistio -- mismo texto semilla que carga esa migración.
_MOTIVO_NO_ASISTIO_AUTOMATICO = "Paciente no se presentó"


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def enviar_recordatorios_proximos(self):
    """
    Diario a las 8am.

    Envía recordatorio a citas en ventana:
    now + 23h  <= fecha_hora <= now + 25h

    No reenvía si ya existe un recordatorio enviado para esa cita.
    """
    ahora = timezone.now()
    desde = ahora + timedelta(hours=23)
    hasta = ahora + timedelta(hours=25)

    notif_svc = NotificacionCitaService()

    citas = (
        CitaMedica.objects.filter(
            fecha_hora__gte=desde,
            fecha_hora__lte=hasta,
            estatus__in=[EstatusCita.AGENDADA, EstatusCita.CONFIRMADA],
        )
        .order_by("fecha_hora")
    )

    enviados = 0
    errores = 0
    revisadas = 0

    for cita in citas:
        revisadas += 1

        notif_orig = (
            cita.notificaciones.filter(
                tipo="confirmacion",
                enviado=True,
            )
            .order_by("-created_at")
            .first()
        )
        if not notif_orig or not notif_orig.email_destino:
            continue

        ya_enviado = cita.notificaciones.filter(
            tipo="recordatorio",
            enviado=True,
        ).exists()
        if ya_enviado:
            continue

        try:
            notif_svc.enviar_recordatorio(cita, notif_orig.email_destino)
            enviados += 1
        except Exception as exc:
            logger.exception("Error enviando recordatorio para cita %s: %s", cita.id, exc)
            errores += 1

    logger.info(
        "Recordatorios procesados. revisadas=%s enviados=%s errores=%s ventana=(%s -> %s)",
        revisadas,
        enviados,
        errores,
        desde,
        hasta,
    )
    return {
        "revisadas": revisadas,
        "enviados": enviados,
        "errores": errores,
    }


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def generar_slots_todos_medicos(self):
    """
    Lunes a la 1am.

    Genera slots para los próximos 30 días para todos los médicos activos.
    Idempotente mediante get_or_create.
    """
    citas_repo = CitasRepository()

    medicos = (
        CatMedico.objects.filter(estatus_medico="ACTIVO")
        .order_by("id_usuario_id")
    )

    total_slots = 0
    total_medicos = 0
    errores = 0

    for medico in medicos:
        try:
            # generar_slots_medico filtra/crea HorarioDisponible.medico_id
            # (espacio médico, FK a CatMedico) -- se pasa medico.id (PK
            # surrogate), no medico.id_usuario_id (R1).
            creados = citas_repo.generar_slots_medico(
                medico_id=medico.id,
                dias_adelante=30,
            )
            total_slots += creados
            total_medicos += 1
        except Exception as exc:
            errores += 1
            logger.exception("Error generando slots para médico %s: %s", medico.id_medclin, exc)

    logger.info(
        "Generación de slots completada. medicos=%s slots_creados=%s errores=%s",
        total_medicos,
        total_slots,
        errores,
    )
    return {
        "medicos": total_medicos,
        "slots_creados": total_slots,
        "errores": errores,
    }


@shared_task
def marcar_no_asistio():
    """
    Cada hora.

    Citas con fecha_hora <= now - 2h y estatus agendada/confirmada
    pasan a no_asistio.
    """
    ahora = timezone.now()
    limite = ahora - timedelta(hours=2)

    citas = CitaMedica.objects.filter(
        fecha_hora__lte=limite,
        estatus__in=[EstatusCita.AGENDADA, EstatusCita.CONFIRMADA],
    )

    motivo_automatico = MotivoCita.objects.filter(
        name=_MOTIVO_NO_ASISTIO_AUTOMATICO, is_active=True,
    ).first()

    actualizadas = 0
    errores = 0
    # Se recorre una por una (en vez de un .update() masivo) para pasar por
    # CitasRepository.update_estatus(), que libera el slot de HorarioDisponible
    # en la misma transacción — un .update() directo sobre el queryset deja el
    # slot marcado como ocupado para siempre.
    for cita in citas:
        try:
            CitasRepository.update_estatus(
                cita,
                EstatusCita.NO_ASISTIO,
                motivo_cancelacion=motivo_automatico,
                motivo_detalle="Automático: sin confirmación 2 horas después de la hora de la cita.",
                changed_by_id=None,
            )
            actualizadas += 1
        except Exception as exc:
            errores += 1
            logger.exception("Error marcando no_asistio para cita %s: %s", cita.id, exc)

    logger.info(
        "Citas marcadas como no_asistio: %s errores=%s (limite=%s)",
        actualizadas, errores, limite,
    )
    return {"actualizadas": actualizadas, "errores": errores}