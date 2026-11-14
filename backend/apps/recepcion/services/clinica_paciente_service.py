"""
Clínica del derechohabiente: solo se agenda en consultorios de su clínica.
La usan recepción (``WRONG_CLINIC``) y el portal (``CLINICA_NO_CORRESPONDE``).

``CD_CLINICA`` de SERMED (fila de ``buscar_expediente``) se traduce al
centro de SIRES con la equivalencia de P-03 (``adscripcion_clinica_centro``).
Si la clave no tiene equivalencia activa se compara con el id del
``CatCentroAtencion``, como hacía recepción antes de P-03.

Sin dato de clínica en SERMED (o centro sin asignar) NO se bloquea.
"""

from collections.abc import Callable

from apps.catalogos.models import CatCentroAtencion
from apps.recepcion.models import AdscripcionClinicaCentro
from apps.recepcion.services.vigencia_service import buscar_fila_paciente


def centro_de_fila(fila: dict | None) -> str | None:
    """Clínica de una fila ya consultada (evita otra consulta a SERMED)."""
    cd_clinica = fila.get("CD_CLINICA") if fila else None
    if cd_clinica in (None, ""):
        return None
    return str(cd_clinica).strip()


def centro_del_paciente(no_exp: str, pk_num: int) -> str | None:
    return centro_de_fila(buscar_fila_paciente(no_exp, pk_num))


def regla_de_clinica(centro_paciente: str | None) -> Callable[[object], bool]:
    """
    Qué centros acepta la clínica del paciente. Consulta la equivalencia una
    sola vez, para filtrar listas sin una consulta por centro.
    """
    if centro_paciente is None:
        return lambda centro_id: True
    equivalente = (
        AdscripcionClinicaCentro.objects.filter(clave_clinica_sermed=centro_paciente, esta_activo=True)
        .values_list("centro_id", flat=True)
        .first()
    )
    esperado = str(equivalente) if equivalente is not None else centro_paciente
    return lambda centro_id: centro_id is None or str(centro_id).strip() == esperado


def centro_de_clave(centro_paciente: str | None) -> CatCentroAtencion | None:
    """El centro de SIRES de la clínica del paciente, con la misma regla que ``regla_de_clinica``."""
    if centro_paciente is None:
        return None
    centro_paciente = str(centro_paciente).strip()
    equivalencia = (
        AdscripcionClinicaCentro.objects.select_related("centro")
        .filter(clave_clinica_sermed=centro_paciente, esta_activo=True)
        .first()
    )
    if equivalencia is not None:
        return equivalencia.centro
    if not centro_paciente.isdigit():
        return None
    return CatCentroAtencion.objects.filter(pk=int(centro_paciente)).first()


def centro_permitido(centro_paciente: str | None, centro_id) -> bool:
    return regla_de_clinica(centro_paciente)(centro_id)


def puede_agendar_en_centro(no_exp: str, pk_num: int, centro_id) -> bool:
    return centro_permitido(centro_del_paciente(no_exp, pk_num), centro_id)
