"""Tareas programadas del modulo de autorizaciones (Celery beat)."""
import logging

from celery import shared_task
from django.utils import timezone

from .uses_case.solicitud_use_case import SolicitudUseCase
from .uses_case.vigencia_autorizadores_use_case import avisar_por_vencer, registrar_vencidos

logger = logging.getLogger(__name__)


@shared_task
def vencer_solicitudes_pendientes():
    """
    Cada 15 minutos.

    Solicitudes PENDIENTE con fecha limite cumplida (72 h por defecto,
    configurable por tipo y centro) pasan a VENCIDA. Idempotente.
    """
    vencidas = SolicitudUseCase.vencer_pendientes()
    if vencidas:
        logger.info("Solicitudes de autorizacion vencidas: %s", vencidas)
    return {"vencidas": vencidas}


@shared_task
def escalar_solicitudes_pendientes():
    """
    Cada 15 minutos.

    Pendientes sin respuesta tras las horas de su tipo (24 por defecto): recordatorio
    a los destinatarios y envio a los elegibles que faltaban. Una vez por solicitud.
    """
    escaladas = SolicitudUseCase.escalar_pendientes()
    if escaladas:
        logger.info("Solicitudes de autorizacion escaladas: %s", escaladas)
    return {"escaladas": escaladas}


@shared_task
def revisar_vigencia_autorizadores():
    """
    Diario.

    Aviso de vigencia por vencer (15 dias antes) y registro de vencimientos, al
    autorizador y a quienes pueden renovarlo. Uno por fecha de fin.
    """
    hoy = timezone.localdate()
    resultado = {"porVencer": avisar_por_vencer(hoy), "vencidos": registrar_vencidos(hoy)}
    logger.info("Vigencia de autorizadores: %s", resultado)
    return resultado
