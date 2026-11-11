"""Semaforo del control de cronicos (docs/plans/cronicos-control.md).

Reglas puras, sin base de datos. Limites inclusivos: 130 con meta maxima 130
esta en meta.
"""
from decimal import Decimal

SIN_DATOS = "sin_datos"
DESCONTROLADO = "descontrolado"
INCOMPLETO = "incompleto"
CONTROLADO = "controlado"


def in_goal(value: Decimal | None, goal_min: Decimal | None, goal_max: Decimal | None) -> bool | None:
    """True/False contra la meta; None si no hay valor o el parametro no tiene meta."""
    if value is None or (goal_min is None and goal_max is None):
        return None
    if goal_min is not None and value < goal_min:
        return False
    if goal_max is not None and value > goal_max:
        return False
    return True


def control_status(results: list[bool | None]) -> str:
    """Estado general a partir del semaforo de cada parametro CON meta
    (None = parametro con meta pero sin valor)."""
    measured = [r for r in results if r is not None]
    if not measured:
        return SIN_DATOS
    if not all(measured):
        return DESCONTROLADO
    if len(measured) < len(results):
        return INCOMPLETO
    return CONTROLADO
