"""
Copia tal cual del legado (diseño del 2026-10-27, runbook legado-tres-capas).
SIRES la LEE con SQL directo, sin modelos: es el original, con sus propias
tablas y catalogos. Dos motores posibles (LEGADO_MOTOR):

- "postgresql": base `sisem_legado`, un esquema por base del legado
  (legado_actual, legado_2015...), alias de Django "legado".
- "mysql": el espejo MySQL del legado tal cual (dbclinicas, dbclinicas2015...),
  leido con PyMySQL directo: Django 6 no acepta MySQL anteriores a 8.0.11 y el
  espejo puede ser mas viejo. Variables LEGACY_MYSQL_* (las mismas de los
  comandos del legado).

El resto del codigo usa siempre los nombres LOGICOS (legado_actual,
legado_2015); aca se traducen a la base fisica. Las dos conexiones abren en
solo lectura y solo se aceptan SELECT. Los nombres de esquema y tabla no
pueden ir como parametro de SQL: se validan contra un patron antes de armar
la consulta.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.db import DatabaseError, connections

logger = logging.getLogger(__name__)

ALIAS = "legado"
ESQUEMA_ACTUAL = "legado_actual"
_PREFIJO = "legado_"
_ESQUEMA = re.compile(r"^legado_[a-z0-9_]+$")
_TABLA = re.compile(r"^[a-z][a-z0-9_]*$")
_BASE_MYSQL = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
MENSAJE_NO_DISPONIBLE = "El historial del sistema anterior no está disponible en este momento."


class LegadoNoDisponible(Exception):
    """La copia del legado no esta configurada o no responde."""


def _es_mysql() -> bool:
    return getattr(settings, "LEGADO_MOTOR", "postgresql") == "mysql"


def _mysql() -> dict:
    return getattr(settings, "LEGADO_MYSQL", {}) or {}


def disponible() -> bool:
    if _es_mysql():
        datos = _mysql()
        return bool(datos.get("host") and datos.get("user"))
    return ALIAS in settings.DATABASES


# ── Nombres ──────────────────────────────────────────────────────────────────

def _base_actual() -> str:
    """Nombre fisico de la base actual del legado, o "" si la copia ya usa los
    nombres logicos (legado_actual, legado_2015...). El espejo MySQL siempre
    tiene los originales; una copia en Postgres puede tener cualquiera de los
    dos (LEGADO_ESQUEMA_ACTUAL=dbclinicas si se cargo sin renombrar)."""
    if _es_mysql():
        return _mysql().get("base_actual") or "dbclinicas"
    return getattr(settings, "LEGADO_ESQUEMA_ACTUAL", "") or ""


def _fisico(esquema: str) -> str:
    """legado_actual -> dbclinicas; legado_2015 -> dbclinicas2015 (o igual, sin traduccion)."""
    base = _base_actual()
    if not base:
        return esquema
    fisica = base if esquema == ESQUEMA_ACTUAL else base + esquema[len(_PREFIJO):]
    if not _BASE_MYSQL.match(fisica):
        raise ValueError(f"Nombre de base del legado invalido: {fisica!r}")
    return fisica


def _esquema_logico(base: str) -> str | None:
    """dbclinicas -> legado_actual; dbclinicas2024_a -> legado_2024_a; otra -> None."""
    actual = _base_actual()
    if base == actual:
        return ESQUEMA_ACTUAL
    if base.startswith(actual):
        logico = _PREFIJO + base[len(actual):].lower()
        if _ESQUEMA.match(logico) and logico != ESQUEMA_ACTUAL:
            return logico
    return None


def tabla(esquema: str, nombre: str) -> str:
    """Nombre calificado y entrecomillado, solo si ambos nombres son validos."""
    if not _ESQUEMA.match(esquema or "") or not _TABLA.match(nombre or ""):
        raise ValueError(f"Nombre de esquema o tabla del legado invalido: {esquema!r}.{nombre!r}")
    if _es_mysql():
        return f"`{_fisico(esquema)}`.`{nombre}`"
    return f'"{_fisico(esquema)}"."{nombre}"'


def texto(expresion: str) -> str:
    """La expresion como texto, para comparar columnas de tipos distintos."""
    return f"CAST({expresion} AS CHAR)" if _es_mysql() else f"CAST({expresion} AS text)"


def clave(expresion: str) -> str:
    """Columna lista para compararla con un parametro de texto. En MySQL va tal
    cual: MySQL convierte el parametro y usa el indice; envolverla en CAST
    obliga a recorrer la tabla entera en cada base."""
    return expresion if _es_mysql() else texto(expresion)


def sin_ceros(expresion: str) -> str:
    """El expediente sin ceros a la izquierda (asi compara SIRES). En MySQL la
    columna es numerica: se compara contra valor_expediente() y usa el indice."""
    if _es_mysql():
        return expresion
    return f"ltrim({texto(expresion)}, '0')"


def valor_expediente(no_exp):
    """Parametro para comparar con sin_ceros(): numero en MySQL, texto en Postgres."""
    texto_exp = str(no_exp).strip()
    return int(texto_exp) if _es_mysql() and texto_exp.isdigit() else texto_exp


# ── Consulta ─────────────────────────────────────────────────────────────────

def consultar(sql: str, params=()) -> list[dict]:
    """Filas como dicts. Cualquier falla de la copia se informa como LegadoNoDisponible."""
    if not disponible():
        raise LegadoNoDisponible(MENSAJE_NO_DISPONIBLE)
    if not sql.lstrip().upper().startswith("SELECT"):
        raise ValueError("Al legado solo se le hacen consultas SELECT.")
    if _es_mysql():
        return _consultar_mysql(sql, params)
    try:
        with connections[ALIAS].cursor() as cursor:
            cursor.execute(sql, params)
            columnas = [columna[0] for columna in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    except DatabaseError as exc:
        logger.error("No se pudo consultar la copia del legado: %s", exc)
        raise LegadoNoDisponible(MENSAJE_NO_DISPONIBLE) from exc


def _consultar_mysql(sql: str, params) -> list[dict]:
    import pymysql
    import pymysql.cursors

    datos = _mysql()
    try:
        conexion = pymysql.connect(
            host=datos["host"], port=int(datos.get("port") or 3306),
            user=datos["user"], password=datos.get("password") or "",
            charset="utf8", cursorclass=pymysql.cursors.DictCursor,
            # Si el espejo no responde, la pantalla lo dice rapido en vez de colgarse.
            connect_timeout=3, read_timeout=15, autocommit=True,
        )
    except pymysql.MySQLError as exc:
        logger.error("No se pudo conectar al espejo MySQL del legado: %s", exc)
        raise LegadoNoDisponible(MENSAJE_NO_DISPONIBLE) from exc
    try:
        with conexion.cursor() as cursor:
            try:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
            except pymysql.MySQLError:
                # MySQL anterior a 5.6.5: queda solo la proteccion del usuario de solo SELECT.
                logger.warning("El espejo del legado no acepta sesiones de solo lectura.")
            cursor.execute(sql, list(params) or None)
            return list(cursor.fetchall())
    except pymysql.MySQLError as exc:
        logger.error("No se pudo consultar el espejo MySQL del legado: %s", exc)
        raise LegadoNoDisponible(MENSAJE_NO_DISPONIBLE) from exc
    finally:
        conexion.close()


def esquemas_con_tabla(nombre: str) -> list[str]:
    """Esquemas legado_* que tienen esa tabla (las anuales pueden no tenerla).
    La actual va primero; las anuales, de la mas reciente a la mas vieja."""
    if not _TABLA.match(nombre or ""):
        raise ValueError(f"Nombre de tabla del legado invalido: {nombre!r}")
    base = _base_actual()
    if base:
        filas = consultar(
            "SELECT table_schema AS esquema FROM information_schema.tables "
            "WHERE table_name = %s AND table_schema LIKE %s",
            [nombre, base.replace("_", "\\_") + "%"],
        )
        validos = [e for e in (_esquema_logico(f["esquema"]) for f in filas) if e]
    else:
        filas = consultar(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = %s AND table_schema LIKE %s",
            [nombre, "legado\\_%"],
        )
        validos = [f["table_schema"] for f in filas if _ESQUEMA.match(f["table_schema"])]
    anuales = sorted((esquema for esquema in validos if esquema != ESQUEMA_ACTUAL), reverse=True)
    return ([ESQUEMA_ACTUAL] if ESQUEMA_ACTUAL in validos else []) + anuales
