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

from apps.administracion.use_cases.expedientes.buscar_expediente import buscar_expediente

logger = logging.getLogger(__name__)

ESTATUS_VIGENTE = "ACTIVO"

MENSAJE_SIN_VIGENCIA_PORTAL = "No encontramos vigencia activa. Acudí a tu clínica."


def buscar_fila_paciente(no_exp: str, pk_num: int) -> dict | None:
    """Fila de ``buscar_expediente`` del titular (pk_num 0) o del familiar."""
    resultado = buscar_expediente(no_exp, incluir_fotos=False)
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
    return fila_tiene_vigencia(buscar_fila_paciente(no_exp, pk_num), no_exp, pk_num)
