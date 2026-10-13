"""
Servicio de notificaciones para citas médicas.
"""

import logging

from apps.medicos.identity import display_name
from apps.recepcion.models import CitaMedica, CitaNotificacion

logger = logging.getLogger(__name__)


class NotificacionCitaService:

    def enviar_confirmacion(self, cita: CitaMedica, email: str) -> CitaNotificacion:
        """Registra y envía correo de confirmación de cita."""
        notif = CitaNotificacion.objects.create(
            cita=cita,
            tipo="confirmacion",
            email_destino=email,
        )
        try:
            self._enviar(
                destinatario=email,
                asunto=f"Confirmación de cita — {cita.folio}",
                cuerpo=self._cuerpo_confirmacion(cita),
            )
            from django.utils import timezone
            notif.enviado    = True
            notif.enviado_at = timezone.now()
            notif.save(update_fields=["enviado", "enviado_at"])
        except Exception:
            logger.exception("Error enviando confirmación para cita %s", cita.id)

        return notif

    def enviar_recordatorio(self, cita: CitaMedica, email: str) -> CitaNotificacion:
        """Registra y envía correo de recordatorio 24h antes."""
        notif = CitaNotificacion.objects.create(
            cita=cita,
            tipo="recordatorio",
            email_destino=email,
        )
        try:
            self._enviar(
                destinatario=email,
                asunto=f"Recordatorio de cita mañana — {cita.folio}",
                cuerpo=self._cuerpo_recordatorio(cita),
            )
            from django.utils import timezone
            notif.enviado    = True
            notif.enviado_at = timezone.now()
            notif.save(update_fields=["enviado", "enviado_at"])
        except Exception:
            logger.exception("Error enviando recordatorio para cita %s", cita.id)

        return notif

    # ── Internos ──────────────────────────────────────────────────────────────

    def _enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None:
        """Envía el correo. Implementación real pendiente de configuración SMTP."""
        from django.core.mail import send_mail
        from django.conf import settings

        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sisem.mx"),
            recipient_list=[destinatario],
            fail_silently=False,
        )

    def _cuerpo_confirmacion(self, cita: CitaMedica) -> str:
        nombre_medico = display_name(cita.medico)
        return (
            f"Su cita ha sido confirmada.\n\n"
            f"Folio:   {cita.folio}\n"
            f"Médico:  Dr(a). {nombre_medico}\n"
            f"Fecha:   {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}\n"
            f"Motivo:  {cita.motivo or 'No especificado'}\n\n"
            "Por favor preséntese 10 minutos antes de su cita."
        )

    def _cuerpo_recordatorio(self, cita: CitaMedica) -> str:
        nombre_medico = display_name(cita.medico)
        return (
            f"Le recordamos que tiene una cita mañana.\n\n"
            f"Folio:   {cita.folio}\n"
            f"Médico:  Dr(a). {nombre_medico}\n"
            f"Fecha:   {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}\n\n"
            "Si no puede asistir, por favor comuníquese con recepción."
        )
