"""Tareas programadas del modulo de autorizaciones (Celery beat)."""
import logging

from celery import shared_task

from .uses_case.solicitud_use_case import SolicitudUseCase

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
