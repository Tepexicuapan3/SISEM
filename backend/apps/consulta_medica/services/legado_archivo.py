"""
Copia tal cual del legado (diseño del 2026-10-27, runbook legado-tres-capas):
base Postgres `sisem_legado`, un esquema por base del legado (legado_actual,
legado_2015...). La actual se recarga cada noche; las anuales, una vez.

SIRES la LEE con SQL directo, sin modelos: es el original, con sus propias
tablas y catalogos. La conexion (alias "legado") abre en solo lectura. Los
nombres de esquema y tabla no pueden ir como parametro de SQL: se validan
contra un patron antes de armar la consulta.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.db import DatabaseError, connections

logger = logging.getLogger(__name__)

ALIAS = "legado"
ESQUEMA_ACTUAL = "legado_actual"
_ESQUEMA = re.compile(r"^legado_[a-z0-9_]+$")
_TABLA = re.compile(r"^[a-z][a-z0-9_]*$")
MENSAJE_NO_DISPONIBLE = "El historial del sistema anterior no está disponible en este momento."


class LegadoNoDisponible(Exception):
    """La copia del legado no esta configurada o no responde."""


def disponible() -> bool:
    return ALIAS in settings.DATABASES


def tabla(esquema: str, nombre: str) -> str:
    """Nombre calificado y entrecomillado, solo si ambos nombres son validos."""
    if not _ESQUEMA.match(esquema or "") or not _TABLA.match(nombre or ""):
        raise ValueError(f"Nombre de esquema o tabla del legado invalido: {esquema!r}.{nombre!r}")
    return f'"{esquema}"."{nombre}"'


def consultar(sql: str, params=()) -> list[dict]:
    """Filas como dicts. Cualquier falla de la copia se informa como LegadoNoDisponible."""
    if not disponible():
        raise LegadoNoDisponible(MENSAJE_NO_DISPONIBLE)
    try:
        with connections[ALIAS].cursor() as cursor:
            cursor.execute(sql, params)
            columnas = [columna[0] for columna in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    except DatabaseError as exc:
        logger.error("No se pudo consultar la copia del legado: %s", exc)
        raise LegadoNoDisponible(MENSAJE_NO_DISPONIBLE) from exc


def esquemas_con_tabla(nombre: str) -> list[str]:
    """Esquemas legado_* que tienen esa tabla (las anuales pueden no tenerla).
    La actual va primero; las anuales, de la mas reciente a la mas vieja."""
    if not _TABLA.match(nombre or ""):
        raise ValueError(f"Nombre de tabla del legado invalido: {nombre!r}")
    filas = consultar(
        "SELECT table_schema FROM information_schema.tables "
        "WHERE table_name = %s AND table_schema LIKE %s",
        [nombre, "legado\\_%"],
    )
    validos = [f["table_schema"] for f in filas if _ESQUEMA.match(f["table_schema"])]
    anuales = sorted((esquema for esquema in validos if esquema != ESQUEMA_ACTUAL), reverse=True)
    return ([ESQUEMA_ACTUAL] if ESQUEMA_ACTUAL in validos else []) + anuales
