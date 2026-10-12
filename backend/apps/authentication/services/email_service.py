import logging
import threading

from django.conf import settings
from django.core.mail import send_mail, get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.authentication.services.otp_service import OTP_TTL_SECONDS

logger = logging.getLogger(__name__)


def send_reset_code_email(recipient_email, code, user_name=None):
    # Envía el código OTP por correo.
    if not _smtp_is_configured():
        logger.warning("SMTP no configurado para enviar OTP")
        return True

    subject = "Código de recuperación"
    safe_name = user_name or recipient_email
    expiration_minutes = max(1, int(OTP_TTL_SECONDS / 60))
    support_email = _setting_value(
        "SISEM_SUPPORT_EMAIL",
        settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
        primary_default=settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
    )
    message = (
        f"Hola {safe_name}, recibimos una solicitud para restablecer la contraseña de tu cuenta.\n\n"
        "Tu código de verificación es: "
        f"{code}\n"
        f"Válido por {expiration_minutes} minutos.\n\n"
        "Si no solicitaste este código, puedes ignorar este correo con tranquilidad.\n"
        f"Soporte: {support_email}"
    )
    company_name = getattr(settings, "EMAIL_COMPANY_NAME", "SISEM STC Metro")
    logo_url = getattr(
        settings,
        "EMAIL_LOGO_URL",
        "https://i.ibb.co/zhdkzrZp/SISEM.webp",
    )
    metro_logo_url = getattr(
        settings,
        "EMAIL_METRO_LOGO_URL",
        "https://i.ibb.co/zhdc3v4c/metro-logo-borde.jpg",
    )
    html_message = render_to_string(
        "authentication/reset_code_email.html",
        {
            "user_name": safe_name,
            "verification_code": code,
            "company_name": company_name,
            "current_year": timezone.now().year,
            "expiration_minutes": expiration_minutes,
            "logo_url": logo_url,
            "metro_logo_url": metro_logo_url,
            "support_email": support_email,
        },
    )
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
            html_message=html_message,
        )
    except Exception:
        # No exponer fallas SMTP al usuario final.
        logger.exception("Fallo al enviar OTP")
        return False

    return True


def send_user_credentials_email(
    recipient_email, username, temporary_password, user_name=None
):
    if not _smtp_is_configured():
        logger.error("SMTP no configurado para enviar credenciales de usuario")
        return False

    safe_name = user_name or username or recipient_email
    subject = "Credenciales de acceso a SISEM"
    login_url = _setting_value(
        "SISEM_LOGIN_URL",
        "http://localhost:5173/login",
        primary_default="http://localhost:5173/login",
    )
    support_email = _setting_value(
        "SISEM_SUPPORT_EMAIL",
        settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
        primary_default=settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
    )
    company_name = getattr(settings, "EMAIL_COMPANY_NAME", "SISEM STC Metro")
    logo_url = getattr(
        settings,
        "EMAIL_LOGO_URL",
        "https://i.ibb.co/zhdkzrZp/SISEM.webp",
    )
    metro_logo_url = getattr(
        settings,
        "EMAIL_METRO_LOGO_URL",
        "https://i.ibb.co/zhdc3v4c/metro-logo-borde.jpg",
    )

    message = (
        f"Hola {safe_name}, tu cuenta de SISEM fue creada.\n\n"
        f"Usuario: {username}\n"
        f"Contraseña temporal: {temporary_password}\n\n"
        "Pasos para acceder:\n"
        f"1. Ingresa a {login_url}\n"
        "2. Inicia sesión con las credenciales temporales.\n"
        "3. Cambia tu contraseña en el primer acceso.\n\n"
        "Recomendaciones de seguridad:\n"
        "- No compartas estas credenciales.\n"
        "- Usa una contraseña única al cambiarla.\n"
        "- Si no reconoces esta alta, repórtala de inmediato.\n"
        f"- Soporte: {support_email}\n"
    )
    html_message = render_to_string(
        "authentication/new_user_credentials_email.html",
        {
            "user_name": safe_name,
            "username": username,
            "temporary_password": temporary_password,
            "login_url": login_url,
            "support_email": support_email,
            "company_name": company_name,
            "current_year": timezone.now().year,
            "logo_url": logo_url,
            "metro_logo_url": metro_logo_url,
        },
    )

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
            html_message=html_message,
        )
    except Exception:
        logger.exception("Fallo al enviar correo de credenciales")
        return False

    return True


def send_user_credentials_email_batch(users, on_progress=None):
    """
    Envia credenciales de alta a varios usuarios reusando una sola conexion
    SMTP (en vez de abrir/cerrar una por usuario como `send_mail`) -- pensado
    para el import masivo, donde el alta ya se hizo y confirmo en la BD, y
    esto corre despues, fuera de esa transaccion.
    users: [{"email": str, "username": str, "temporary_password": str, "user_name": str}, ...]
    on_progress: callable opcional `(procesados: int)` llamado tras cada usuario.
    Devuelve {"sent": N, "failed": [{"username": ..., "email": ...}]}

    Si un envio falla se reabre la conexion y se reintenta UNA vez: muchos
    servidores SMTP cortan la conexion tras N mensajes, y sin esto en un
    lote de miles todos los correos posteriores al corte fallarian.
    """
    if not users:
        return {"sent": 0, "failed": []}

    if not _smtp_is_configured():
        logger.error("SMTP no configurado para enviar credenciales de usuario (batch)")
        return {
            "sent": 0,
            "failed": [{"username": u["username"], "email": u["email"]} for u in users],
        }

    login_url = _setting_value(
        "SISEM_LOGIN_URL",
        "http://localhost:5173/login",
        primary_default="http://localhost:5173/login",
    )
    support_email = _setting_value(
        "SISEM_SUPPORT_EMAIL",
        settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
        primary_default=settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
    )
    company_name = getattr(settings, "EMAIL_COMPANY_NAME", "SISEM STC Metro")
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "https://i.ibb.co/zhdkzrZp/SISEM.webp")
    metro_logo_url = getattr(settings, "EMAIL_METRO_LOGO_URL", "https://i.ibb.co/zhdc3v4c/metro-logo-borde.jpg")
    current_year = timezone.now().year
    subject = "Credenciales de acceso a SISEM"

    sent = 0
    failed = []
    conn = None

    def _reopen():
        nonlocal conn
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        conn = get_connection()
        conn.open()

    try:
        _reopen()
        for processed, u in enumerate(users, start=1):
            safe_name = u.get("user_name") or u["username"] or u["email"]
            try:
                message = (
                    f"Hola {safe_name}, tu cuenta de SISEM fue creada.\n\n"
                    f"Usuario: {u['username']}\n"
                    f"Contraseña temporal: {u['temporary_password']}\n\n"
                    "Pasos para acceder:\n"
                    f"1. Ingresa a {login_url}\n"
                    "2. Inicia sesión con las credenciales temporales.\n"
                    "3. Cambia tu contraseña en el primer acceso.\n\n"
                    "Recomendaciones de seguridad:\n"
                    "- No compartas estas credenciales.\n"
                    "- Usa una contraseña única al cambiarla.\n"
                    "- Si no reconoces esta alta, repórtala de inmediato.\n"
                    f"- Soporte: {support_email}\n"
                )
                html = render_to_string(
                    "authentication/new_user_credentials_email.html",
                    {
                        "user_name": safe_name,
                        "username": u["username"],
                        "temporary_password": u["temporary_password"],
                        "login_url": login_url,
                        "support_email": support_email,
                        "company_name": company_name,
                        "current_year": current_year,
                        "logo_url": logo_url,
                        "metro_logo_url": metro_logo_url,
                    },
                )
                email_msg = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[u["email"]],
                    connection=conn,
                )
                email_msg.attach_alternative(html, "text/html")
                try:
                    email_msg.send()
                except Exception:
                    logger.warning(
                        "Fallo envio a %s; reabriendo conexion SMTP y reintentando",
                        u.get("email"),
                    )
                    _reopen()
                    email_msg.connection = conn
                    email_msg.send()
                sent += 1
            except Exception:
                logger.exception("Fallo al enviar credenciales a %s", u.get("email"))
                failed.append({"username": u["username"], "email": u["email"]})
            if on_progress is not None:
                on_progress(processed)
    except Exception:
        logger.exception("Fallo al abrir conexión SMTP para credenciales (batch)")
        # Todo usuario que no llego a enviarse ni a fallar queda como fallido
        # (antes solo se cubria el caso "fallo antes del primer envio").
        handled = sent + len(failed)
        failed.extend(
            {"username": u["username"], "email": u["email"]} for u in users[handled:]
        )
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    logger.info("Credenciales batch: %d enviados, %d fallidos", sent, len(failed))
    return {"sent": sent, "failed": failed}


def send_notification_email_batch(recipients, subject, message, category="Notificación SISEM", attachments=None):
    """
    Envía una notificación masiva de forma síncrona con una sola conexión SMTP.
    recipients:  [{"email": str, "name": str, "username": str}, ...]
    attachments: [(filename: str, content: bytes, mimetype: str), ...] | None
    Devuelve {"sent": N, "failed": [{"username": ..., "name": ..., "email": ...}]}
    """
    if not recipients:
        return {"sent": 0, "failed": []}

    company_name = getattr(settings, "EMAIL_COMPANY_NAME", "SISEM STC Metro")
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "https://i.ibb.co/zhdkzrZp/SISEM.webp")
    metro_logo_url = getattr(settings, "EMAIL_METRO_LOGO_URL", "https://i.ibb.co/zhdc3v4c/metro-logo-borde.jpg")
    support_email = _setting_value(
        "SISEM_SUPPORT_EMAIL",
        settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
        primary_default=settings.DEFAULT_FROM_EMAIL or "soporte@sisem.local",
    )
    current_year = timezone.now().year

    sent = 0
    failed = []

    try:
        conn = get_connection()
        conn.open()
        for recipient in recipients:
            try:
                html = render_to_string(
                    "authentication/notification_email.html",
                    {
                        "user_name": recipient["name"],
                        "subject": subject,
                        "message": message,
                        "category": category,
                        "company_name": company_name,
                        "logo_url": logo_url,
                        "metro_logo_url": metro_logo_url,
                        "support_email": support_email,
                        "current_year": current_year,
                    },
                )
                email_msg = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient["email"]],
                    connection=conn,
                )
                email_msg.attach_alternative(html, "text/html")
                if attachments:
                    for filename, content, mimetype in attachments:
                        email_msg.attach(filename, content, mimetype or "application/octet-stream")
                email_msg.send()
                sent += 1
            except Exception:
                logger.exception("Fallo al enviar notificación a %s", recipient.get("email"))
                failed.append({
                    "username": recipient.get("username", ""),
                    "name": recipient.get("name", ""),
                    "email": recipient.get("email", ""),
                })
    except Exception:
        logger.exception("Fallo al abrir conexión SMTP para notificación masiva")
        # Si la conexión falló por completo, todos son fallidos
        if sent == 0 and not failed:
            failed = [
                {"username": r.get("username", ""), "name": r.get("name", ""), "email": r.get("email", "")}
                for r in recipients
            ]
    finally:
        try:
            conn.close()
        except Exception:
            pass

    logger.info("Notificación masiva: %d enviados, %d fallidos", sent, len(failed))
    return {"sent": sent, "failed": failed}


def _smtp_is_configured():
    if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        return True

    return bool(
        settings.EMAIL_HOST
        and settings.EMAIL_HOST_USER
        and settings.EMAIL_HOST_PASSWORD
    )


def _setting_value(primary_key, default, primary_default=None):
    primary_value = getattr(settings, primary_key, None)
    if primary_value and (primary_default is None or primary_value != primary_default):
        return primary_value

    return primary_value or default
