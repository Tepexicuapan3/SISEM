"""
Plan identidad del paciente, Fase 1 (docs/plans/identidad-paciente.md):
reglas del alta de un registro de paciente (cns_paciente). La unica puerta de
entrada es PatientRepository.get_or_create, que aplica esto:

  - normalizar_no_exp: sin espacios ni ceros a la izquierda. Para la
    restriccion unica "40041" y " 40041" son dos valores distintos: sin
    normalizar nacerian dos registros de la misma afiliacion.
  - verificar_alta: el no_exp/pk_num tiene que existir en la replica de
    SERMED (sin pacientes fantasmas), segun
    settings.IDENTIDAD_PACIENTE["VERIFICAR_SERMED"]:
        apagado  -> como antes, no se consulta.
        observar -> se crea igual y queda un AuditoriaEvento para revisar.
        bloquear -> no se crea (409 PATIENT_NOT_IN_SERMED).

Solo se verifica el origen ATENCION. El legado no: trae la historia de
personas que pueden ya no estar en SERMED (bajas, fallecidos) y esa historia
se conserva por retencion legal. La regularizacion (vincular_id_paciente)
tampoco: los registros clinicos ya existen. Si la replica no responde, no se
bloquea: una caida de SERMED no deja a nadie sin atencion (mismo criterio que
recepcion.services.vigencia_service).
"""
from __future__ import annotations

import logging

from django.conf import settings

from apps.recepcion.services.errors import VisitDomainError

logger = logging.getLogger(__name__)

ORIGEN_ATENCION = "ATENCION"
ORIGEN_LEGADO = "LEGADO"
ORIGEN_REGULARIZACION = "REGULARIZACION"

ACCION_OBSERVADA = "PatientCreatedNotInSermed"
CODIGO_NO_EN_SERMED = "PATIENT_NOT_IN_SERMED"


def normalizar_no_exp(no_exp) -> str:
    """'040041' y ' 40041 ' -> '40041'. Lo que no es numerico solo se recorta."""
    texto = str(no_exp).strip()
    if texto.isdigit():
        texto = str(int(texto))
    return texto


def modo_verificacion() -> str:
    return settings.IDENTIDAD_PACIENTE.get("VERIFICAR_SERMED", "apagado")


def existe_en_sermed(no_exp: str, pk_num: int) -> bool | None:
    """True/False segun la replica; None si no se pudo consultar."""
    from apps.administracion.models import CatEmpleado, CatFamiliar

    try:
        if pk_num == 0:
            return CatEmpleado.objects.filter(no_exp=no_exp).exists()
        return CatFamiliar.objects.filter(pk_num=pk_num, no_expf=no_exp).exists()
    except Exception:
        logger.warning(
            "No se pudo verificar en SERMED %s/%s; no se bloquea el alta.", no_exp, pk_num, exc_info=True,
        )
        return None


def _registrar_observacion(no_exp: str, pk_num: int, *, origen: str, created_by_id) -> None:
    """Deja constancia de un alta que en modo bloquear no se habria permitido.
    Nunca rompe la atencion: un fallo aqui solo se loguea."""
    from apps.administracion.models import AuditoriaEvento

    try:
        AuditoriaEvento.objects.create(
            request_id="",
            accion=ACCION_OBSERVADA,
            recurso_tipo="cns_paciente",
            actor_usuario_id=created_by_id,
            actor_nombre=None if created_by_id else "Sistema",
            resultado=AuditoriaEvento.Resultado.SUCCESS,
            codigo_error=CODIGO_NO_EN_SERMED,
            meta={"noExp": no_exp, "pkNum": pk_num, "origen": origen, "modo": "observar"},
        )
    except Exception:
        logger.exception("No se pudo registrar el alta observada %s/%s", no_exp, pk_num)
    logger.warning("Alta de paciente que no esta en SERMED (modo observar): %s/%s", no_exp, pk_num)


def verificar_alta(no_exp: str, pk_num, *, origen: str, created_by_id=None) -> None:
    """
    Se llama justo antes de CREAR un registro (nunca cuando ya existe).
    Lanza VisitDomainError solo en modo bloquear y si SERMED confirma que no
    existe.
    """
    modo = modo_verificacion()
    # pk_num None = familiar del legado identificado por cd_familiar: no esta en SERMED.
    if modo == "apagado" or origen != ORIGEN_ATENCION or pk_num is None:
        return
    if existe_en_sermed(no_exp, pk_num) is not False:
        return
    if modo == "observar":
        _registrar_observacion(no_exp, pk_num, origen=origen, created_by_id=created_by_id)
        return
    persona = "el trabajador" if pk_num == 0 else f"el familiar {pk_num}"
    raise VisitDomainError(
        CODIGO_NO_EN_SERMED,
        f"El expediente {no_exp} ({persona}) no existe en SERMED. Actualizá el expediente "
        "desde Administración → Expedientes; si sigue sin aparecer, Capital Humano tiene que darlo de alta.",
        409,
        details={"noExp": no_exp, "pkNum": pk_num},
    )
