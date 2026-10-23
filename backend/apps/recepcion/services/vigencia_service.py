"""
Vigencia del derechohabiente para agendar y atender.

Reusa la regla que ya calcula ``buscar_expediente`` en SQL (``ESTATUS``:
``ACTIVO`` / ``BAJA`` para el titular, ``ACTIVO`` / ``NO ACTIVO`` para el
familiar según ``fec_vig``), la misma que usa recepción para mostrar solo
miembros activos en el check-in sin cita (``visit_queue_usecase.lookup_patient``).

Si no se puede verificar (el expediente no aparece o la base de expedientes
no responde: ``buscar_expediente`` devuelve vacío en los dos casos) NO se
bloquea, solo se deja un warning. Mismo criterio que
``clinica_paciente_service`` ("sin dato en SERMED -> no bloqueamos"): una
caída de SERMED no debe dejar sin atención a todos.
"""

import logging

from apps.administracion.use_cases.expedientes.buscar_expediente import ExpedientesNoDisponible, buscar_expediente

logger = logging.getLogger(__name__)

ESTATUS_VIGENTE = "ACTIVO"

MENSAJE_SIN_VIGENCIA_PORTAL = "No encontramos vigencia activa. Acudí a tu clínica."


def buscar_fila_paciente(no_exp: str, pk_num: int) -> dict | None:
    """Fila de ``buscar_expediente`` del titular (pk_num 0) o del familiar."""
    try:
        resultado = buscar_expediente(no_exp, incluir_fotos=False)
    except ExpedientesNoDisponible:
        # Misma regla que antes (no bloquear si SERMED no responde), pero ya no
        # en silencio: es una falla tecnica que alguien tiene que atender.
        logger.error(
            "VIGENCIA NO VERIFICADA: la replica de SERMED no respondio para %s/%s; "
            "se permite continuar.", no_exp, pk_num,
        )
        return None
    if pk_num == 0:
        empleados = resultado.get("empleados", [])
        return empleados[0] if empleados else None
    return next(
        (
            f for f in resultado.get("familiares", [])
            if str(f.get("PK_NUM")) == str(pk_num)
        ),
        None,
    )


def fila_tiene_vigencia(fila: dict | None, no_exp: str, pk_num: int) -> bool:
    if fila is None:
        logger.warning(
            "No se pudo verificar la vigencia de %s/%s; no se bloquea.", no_exp, pk_num,
        )
        return True
    return fila.get("ESTATUS") == ESTATUS_VIGENTE


def tiene_vigencia(no_exp: str, pk_num: int) -> bool:
    # Plan identidad, bloque C2: el recien nacido provisional no esta en SERMED;
    # su vigencia es la del provisional (regla del legado: hoy + 60 dias).
    from apps.consulta_medica.services import newborn_service

    if newborn_service.es_clave_provisional(pk_num):
        provisional = newborn_service.provisional_por_clave(no_exp, pk_num)
        return provisional is not None and newborn_service.vigente(provisional)
    return fila_tiene_vigencia(buscar_fila_paciente(no_exp, pk_num), no_exp, pk_num)
