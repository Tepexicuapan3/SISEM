"""
apps/portal_citas/uses_case/iniciar_sesion_usecase.py
========================================================
Primer paso del login del portal: resuelve identidad y decide si hace
falta capturar correo (primera vez / quedó a medias) o si ya puede
mandarse un OTP nuevo al correo ya verificado.
"""

from apps.portal_citas.errors import PortalAuthError
from apps.portal_citas.models import PortalMiembro, PortalOTP
from apps.portal_citas.services.email_service import send_otp_email
from apps.portal_citas.services.identity_service import resolve_identity
from apps.portal_citas.services.otp_service import generate_code, hash_code, nueva_expiracion
from apps.recepcion.services.vigencia_service import MENSAJE_SIN_VIGENCIA_PORTAL, tiene_vigencia


def validar_vigencia_login(identidad) -> None:
    """
    Sin vigencia no se entra al portal. Va después de resolver la identidad:
    quien llega acá ya dio expediente, nombre y fecha de nacimiento
    correctos, así que el mensaje puede decirle qué hacer.
    """
    if not tiene_vigencia(identidad.no_exp, identidad.pk_num):
        raise PortalAuthError("SIN_VIGENCIA", MENSAJE_SIN_VIGENCIA_PORTAL, 403)


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    return f"{name[:1]}***@{domain}"


def iniciar_sesion(no_exp, nombre_completo, fecha_nacimiento):
    identidad = resolve_identity(no_exp, nombre_completo, fecha_nacimiento)
    if identidad is None:
        raise PortalAuthError(
            "IDENTIDAD_NO_ENCONTRADA",
            "No pudimos verificar tus datos. Revisa tu número de expediente, "
            "nombre completo y fecha de nacimiento.",
            401,
        )

    if identidad.es_menor_de_edad:
        raise PortalAuthError(
            "MENOR_DE_EDAD",
            "Un menor de edad no puede iniciar sesión por su cuenta; debe "
            "gestionarlo un adulto del núcleo familiar.",
            403,
        )

    validar_vigencia_login(identidad)

    miembro, _creado = PortalMiembro.objects.get_or_create(
        no_exp=identidad.no_exp,
        pk_num=identidad.pk_num,
        defaults={
            "nombre_visible": identidad.nombre_visible,
            "es_titular_login": identidad.es_titular,
        },
    )

    # Si el nombre/rol cambió en el catálogo desde el alta, lo refresca.
    campos_actualizados = []
    if miembro.nombre_visible != identidad.nombre_visible:
        miembro.nombre_visible = identidad.nombre_visible
        campos_actualizados.append("nombre_visible")
    if miembro.es_titular_login != identidad.es_titular:
        miembro.es_titular_login = identidad.es_titular
        campos_actualizados.append("es_titular_login")
    if campos_actualizados:
        miembro.save(update_fields=[*campos_actualizados, "updated_at"])

    if not miembro.correo_verificado or not miembro.correo:
        return {"requiereCorreo": True}

    codigo = generate_code()
    PortalOTP.objects.create(
        portal_miembro=miembro,
        correo_destino=miembro.correo,
        codigo_hash=hash_code(codigo),
        expira_en=nueva_expiracion(),
    )
    if not send_otp_email(miembro.correo, codigo, member_name=miembro.nombre_visible):
        raise PortalAuthError(
            "ENVIO_CORREO_FALLIDO",
            "No se pudo enviar el código de verificación. Intenta de nuevo.",
            500,
        )

    return {"requiereCorreo": False, "correoEnmascarado": mask_email(miembro.correo)}
