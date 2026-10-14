"""
apps/portal_citas/uses_case/capturar_correo_usecase.py
==========================================================
Segundo paso (solo cuando iniciar_sesion respondió requiereCorreo=True):
re-resuelve identidad, guarda el correo del miembro (sin marcarlo
verificado todavía) y dispara el primer OTP.
"""

from apps.portal_citas.errors import PortalAuthError
from apps.portal_citas.models import PortalMiembro, PortalOTP
from apps.portal_citas.services.email_service import send_otp_email
from apps.portal_citas.services.identity_service import resolve_identity
from apps.portal_citas.services.otp_service import generate_code, hash_code, nueva_expiracion
from apps.portal_citas.uses_case.iniciar_sesion_usecase import mask_email, validar_vigencia_login


def capturar_correo(no_exp, nombre_completo, fecha_nacimiento, correo):
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

    miembro.correo = correo
    miembro.correo_verificado = False
    miembro.save(update_fields=["correo", "correo_verificado", "updated_at"])

    codigo = generate_code()
    PortalOTP.objects.create(
        portal_miembro=miembro,
        correo_destino=correo,
        codigo_hash=hash_code(codigo),
        expira_en=nueva_expiracion(),
    )
    if not send_otp_email(correo, codigo, member_name=miembro.nombre_visible):
        raise PortalAuthError(
            "ENVIO_CORREO_FALLIDO",
            "No se pudo enviar el código de verificación. Intenta de nuevo.",
            500,
        )

    return {"correoEnmascarado": mask_email(correo)}
