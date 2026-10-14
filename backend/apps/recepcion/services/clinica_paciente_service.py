"""
Clínica del derechohabiente: solo se agenda en consultorios de su clínica.

``CD_CLINICA`` de SERMED (fila de ``buscar_expediente``) se compara con el
id del ``CatCentroAtencion`` del consultorio, como siempre hizo recepción
(antes vivía en ``citas_views._validar_clinica_paciente``). Ahora lo usa
también el portal.

Sin dato de clínica en SERMED (o centro sin asignar) NO se bloquea.
"""

from apps.recepcion.services.vigencia_service import buscar_fila_paciente


def centro_de_fila(fila: dict | None) -> str | None:
    """Clínica de una fila ya consultada (evita otra consulta a SERMED)."""
    cd_clinica = fila.get("CD_CLINICA") if fila else None
    if cd_clinica in (None, ""):
        return None
    return str(cd_clinica).strip()


def centro_del_paciente(no_exp: str, pk_num: int) -> str | None:
    return centro_de_fila(buscar_fila_paciente(no_exp, pk_num))


def centro_permitido(centro_paciente: str | None, centro_id) -> bool:
    if centro_paciente is None or centro_id is None:
        return True
    return centro_paciente == str(centro_id).strip()


def puede_agendar_en_centro(no_exp: str, pk_num: int, centro_id) -> bool:
    return centro_permitido(centro_del_paciente(no_exp, pk_num), centro_id)
