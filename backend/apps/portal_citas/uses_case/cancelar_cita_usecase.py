"""
apps/portal_citas/uses_case/cancelar_cita_usecase.py
=========================================================
Cancelación de cita del portal de autoservicio (Fase 6).

Flujo (validaciones en este orden):

1. Se busca la ``CitaMedica`` por ``folio``. Si no existe -> 404 genérico.
2. Autorización: se resuelve el ``PortalMiembro`` dueño de la cita a partir
   de ``cita.no_exp``/``cita.pk_num`` (misma tupla que identifica a un
   miembro del núcleo, ver ``apps.portal_citas.models.PortalMiembro`` y
   ``services.nucleo_service``) y se reusa
   ``services.nucleo_service.puede_gestionar_miembro`` (misma regla que la
   reserva de Fase 4 y el núcleo de Fase 3) para confirmar que la sesión
   actual puede gestionar a ese paciente. Si el miembro no existe o no está
   autorizado -> 403 genérico, sin distinguir el motivo.
3. Estado válido: solo se puede cancelar una cita en ``agendada`` o
   ``confirmada`` -- si ya está ``atendida``, ``cancelada`` o
   ``no_asistio`` -> 409.
4. Ventana mínima de tiempo: si falta menos de
   ``settings.PORTAL_CANCELACION_VENTANA_HORAS`` para ``fecha_hora`` -> 409.
5. Transacción atómica (mismo patrón que
   ``reservar_cita_usecase.reservar_cita``, con ``select_for_update()``):
   se bloquea la ``CitaMedica`` con ``select_for_update()`` y se re-valida
   el estatus DESPUÉS de tomar el lock (defensa contra una carrera entre
   el chequeo del paso 3, sin lock, y este punto -- ej. dos pestañas
   cancelando la misma cita al mismo tiempo). El cambio de estatus en sí
   se delega en ``CitasRepository.update_estatus`` (mismo camino que usa
   recepción) dentro de un savepoint anidado -- eso deja
   ``cancelado_en``/``motivo_cancelacion``, libera el
   ``HorarioDisponible`` asociado, y escribe el registro en
   ``CitaEstatusLog`` (bitácora NOM-024). ``changed_by_id=None`` porque es
   autogestionado por el paciente -- no hay usuario de staff detrás
   (mismo criterio que ``created_by_id=None`` en la reserva de Fase 4). Si
   el paciente no escribió un motivo, se usa uno por defecto (la máquina
   de estados exige motivo para cancelar, igual que para recepción).
6. (Fase 6) Ya confirmada la transacción anterior, se encola
   ``tasks.enviar_cancelacion_portal_task`` con ``.delay(...)`` para
   mandar el correo de cancelación en background -- este endpoint NO
   espera a que el correo se envíe para responder, y un fallo de Celery
   nunca debe tumbar la respuesta.
7. Se devuelven solo datos no sensibles (``folio`` + ``estatus``), nunca
   ``no_exp``/``pk_num`` ni datos de otro paciente.

Fuera de alcance (fases posteriores): check-in / validación del QR en
recepción (Fase 7).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalogos.models import MotivoCita
from apps.portal_citas.errors import PortalCancelacionError
from apps.portal_citas.models import PortalMiembro
from apps.portal_citas.services.nucleo_service import puede_gestionar_miembro
from apps.portal_citas.tasks import enviar_cancelacion_portal_task
from apps.recepcion.models import CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import llave_publica

logger = logging.getLogger(__name__)

# Solo se puede cancelar una cita que todavía no ocurrió ni fue resuelta.
ESTATUS_CANCELABLES = (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)

# Motivo tipificado (catálogo MotivoCita, ver migración
# catalogos/0021_motivos_cita) usado cuando el propio paciente cancela
# desde el portal -- no hay UI ahí para elegir un motivo del catálogo, así
# que se resuelve siempre a este valor fijo; lo que el paciente haya
# escrito libremente (si algo) queda como `motivo_detalle`.
_MOTIVO_CANCELACION_PACIENTE = "Cancelada por el paciente"


def _validar_estatus_cancelable(estatus: str) -> None:
    if estatus not in ESTATUS_CANCELABLES:
        raise PortalCancelacionError(
            "ESTADO_NO_CANCELABLE",
            f'La cita está en estatus "{estatus}" y ya no se puede cancelar.',
            409,
        )


def cancelar_cita(
    miembro_sesion: PortalMiembro,
    folio: str,
    motivo: str | None = None,
) -> dict:
    cita = CitaMedica.objects.filter(folio=folio).first()
    if cita is None:
        raise PortalCancelacionError(
            "CITA_NO_ENCONTRADA",
            "La cita no existe.",
            404,
        )

    # No se distingue "miembro no existe" de "no autorizado": mismo mensaje
    # genérico en ambos casos, igual que en la reserva de Fase 4, para no
    # revelar detalles a un atacante que adivinó un folio ajeno.
    # Plan contraer la llave vieja: la llave de la cita sale de cns_paciente.
    no_exp_cita, pk_num_cita = llave_publica(cita)
    miembro_objetivo = PortalMiembro.objects.filter(
        no_exp=no_exp_cita, pk_num=pk_num_cita
    ).first()
    if miembro_objetivo is None or not puede_gestionar_miembro(
        miembro_sesion, miembro_objetivo.id
    ):
        raise PortalCancelacionError(
            "NO_AUTORIZADO",
            "No puedes cancelar esa cita.",
            403,
        )

    _validar_estatus_cancelable(cita.estatus)

    ventana = timedelta(hours=settings.PORTAL_CANCELACION_VENTANA_HORAS)
    if cita.fecha_hora - timezone.now() < ventana:
        raise PortalCancelacionError(
            "FUERA_DE_VENTANA",
            "Ya no se puede cancelar, faltan menos de "
            f"{settings.PORTAL_CANCELACION_VENTANA_HORAS} horas para la cita.",
            409,
        )

    with transaction.atomic():
        cita = CitaMedica.objects.select_for_update().get(id=cita.id)
        # Re-chequeo post-lock: entre la validación de arriba (sin lock) y
        # este punto, otra request pudo haber cancelado/atendido la misma
        # cita primero.
        _validar_estatus_cancelable(cita.estatus)

        # Delega en CitasRepository.update_estatus (mismo camino que usa
        # recepción) en vez de duplicar acá el guardado de
        # cancelado_en/motivo_cancelacion y la liberación del slot -- así la
        # cancelación desde el portal también queda en CitaEstatusLog
        # (bitácora NOM-024), cosa que antes de este cambio no pasaba.
        # transaction.atomic() es reentrante: esto abre un savepoint dentro
        # de la transacción ya iniciada arriba, no una transacción nueva.
        # Autogestionado por el propio paciente/derechohabiente -- no hay
        # usuario de staff detrás, por eso changed_by_id=None (mismo
        # criterio que created_by_id=None en la reserva de Fase 4). Si el
        # paciente no escribió un motivo, se deja uno por defecto: el
        # motivo es obligatorio en la máquina de estados (mismo requisito
        # que para recepción) y no queremos forzar al paciente a escribirlo.
        motivo_catalogo = MotivoCita.objects.filter(
            name=_MOTIVO_CANCELACION_PACIENTE, is_active=True,
        ).first()
        try:
            CitasRepository.update_estatus(
                cita,
                EstatusCita.CANCELADA,
                motivo_cancelacion=motivo_catalogo,
                motivo_detalle=motivo or "Cancelada por el paciente desde el portal.",
                changed_by_id=None,
            )
        except VisitDomainError as exc:
            raise PortalCancelacionError(exc.code, exc.message, exc.status_code) from exc

    # La cancelación ya quedó confirmada (transacción cerrada arriba) -- el
    # envío del correo se dispara async y nunca debe tumbar la respuesta si
    # Celery/Redis no está disponible.
    try:
        enviar_cancelacion_portal_task.delay(
            folio=cita.folio,
            miembro_sesion_id=str(miembro_sesion.id),
        )
    except Exception:
        logger.exception(
            "No se pudo encolar el envío del correo de cancelación portal para folio %s",
            cita.folio,
        )

    return {"folio": cita.folio, "estatus": cita.estatus}
