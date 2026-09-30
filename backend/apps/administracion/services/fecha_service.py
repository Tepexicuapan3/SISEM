"""
Utilidades de fechas para el módulo de expedientes.
"""

from datetime import date, datetime


def calcular_edad(fecha_nacimiento) -> int | None:
    """
    Calcula la edad en años a partir de una fecha de nacimiento.

    Args:
        fecha_nacimiento: ``date``, ``datetime`` o ``str`` en formato ``YYYY-MM-DD``.

    Returns:
        Edad en años como entero, o ``None`` si la fecha es inválida/nula.
    """
    if not fecha_nacimiento:
        return None

    if isinstance(fecha_nacimiento, datetime):
        fecha_nacimiento = fecha_nacimiento.date()
    elif isinstance(fecha_nacimiento, str):
        try:
            fecha_nacimiento = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
        except ValueError:
            return None

    hoy = date.today()
    return (
        hoy.year - fecha_nacimiento.year
        - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    )

