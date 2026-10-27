"""Estado de vigencia de un autorizador. Se calcula al momento, nunca se guarda:
un registro guardado como "vigente" dejaria de serlo sin que nadie lo toque.

Limites inclusivos: el dia de inicio y el dia de fin cuentan como vigentes.
"""
from datetime import date
from enum import Enum

DIAS_AVISO_PREDETERMINADO = 15


class EstadoVigencia(str, Enum):
    PENDIENTE_INICIO = "PENDIENTE_INICIO"
    VIGENTE = "VIGENTE"
    POR_VENCER = "POR_VENCER"
    VENCIDO = "VENCIDO"

    @property
    def habilita(self) -> bool:
        """Solo VIGENTE y POR_VENCER permiten autorizar."""
        return self in (EstadoVigencia.VIGENTE, EstadoVigencia.POR_VENCER)


def estado_vigencia(
    inicio: date, fin: date, hoy: date, dias_aviso: int = DIAS_AVISO_PREDETERMINADO,
) -> EstadoVigencia:
    if hoy < inicio:
        return EstadoVigencia.PENDIENTE_INICIO
    if hoy > fin:
        return EstadoVigencia.VENCIDO
    if (fin - hoy).days <= dias_aviso:
        return EstadoVigencia.POR_VENCER
    return EstadoVigencia.VIGENTE
