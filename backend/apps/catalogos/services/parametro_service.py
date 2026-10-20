"""
Lectura de parametros operativos (contrato para los demas modulos).

``get_param(clave, center_id=..., default=...)`` devuelve el valor ya tipado:
primero el del centro (si la definicion lo admite), si no el general. Si la
definicion no existe o esta inactiva devuelve ``default`` y deja un warning:
asi un despliegue sin la migracion de datos no rompe la operacion.

Cache: UNA entrada por clave con el valor general y todas las excepciones por
centro, asi una escritura invalida una sola clave (TTL corto como respaldo).
"""

import logging
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db import transaction

from ..models import ParametroCentro, ParametroDefinicion

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "catalogos:parametro"
_CACHE_TTL_SECONDS = 60
_MISSING = object()
_UNDEFINED = "__undefined__"
_TRUE = {"true", "1", "s", "si", "sí"}
_FALSE = {"false", "0", "n", "no"}


class ParametroValueError(ValueError):
    """Valor que no respeta el tipo o los limites de la definicion."""


def _cache_key(key):
    return f"{_CACHE_PREFIX}:{key}"


def parse_value(definition, raw):
    """Convierte el texto guardado al tipo de la definicion y valida limites.

    ``definition`` puede ser el modelo o cualquier objeto con value_type,
    min_value y max_value."""
    text = "" if raw is None else str(raw).strip()
    tipo = definition.value_type
    if tipo == ParametroDefinicion.Tipo.TEXTO:
        return text
    if tipo == ParametroDefinicion.Tipo.BOOLEANO:
        lowered = text.lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ParametroValueError("Debe ser verdadero o falso.")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ParametroValueError("Debe ser un número.") from exc
    if not number.is_finite():
        raise ParametroValueError("Debe ser un número.")
    if tipo == ParametroDefinicion.Tipo.ENTERO and number != number.to_integral_value():
        raise ParametroValueError("Debe ser un número entero.")
    if definition.min_value is not None and number < definition.min_value:
        raise ParametroValueError(f"No puede ser menor que {definition.min_value.normalize()}.")
    if definition.max_value is not None and number > definition.max_value:
        raise ParametroValueError(f"No puede ser mayor que {definition.max_value.normalize()}.")
    return int(number) if tipo == ParametroDefinicion.Tipo.ENTERO else number


def normalize_value(definition, raw):
    """Texto canonico para guardar (valida en el camino)."""
    value = parse_value(definition, raw)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _load(key):
    """Snapshot ya tipado: {"general": v, "centers": {id: v}} o _UNDEFINED."""
    definition = ParametroDefinicion.objects.filter(key=key, is_active=True).first()
    if definition is None:
        return _UNDEFINED
    centers = {}
    if definition.allows_center_override:
        for center_id, raw in ParametroCentro.objects.filter(definition=definition).values_list(
            "center_id", "value"
        ):
            try:
                centers[center_id] = parse_value(definition, raw)
            except ParametroValueError:
                logger.error("Parametro %s invalido para el centro %s; se ignora.", key, center_id)
    return {"general": parse_value(definition, definition.general_value), "centers": centers}


def _cache_get(key):
    try:
        return cache.get(_cache_key(key))
    except Exception:  # Redis caido: se lee de la BD, nunca se bloquea la operacion.
        logger.warning("Cache no disponible leyendo el parametro %s.", key, exc_info=True)
        return None


def _cache_set(key, snapshot):
    try:
        cache.set(_cache_key(key), snapshot, _CACHE_TTL_SECONDS)
    except Exception:
        logger.warning("Cache no disponible guardando el parametro %s.", key, exc_info=True)


def get_param(key, *, center_id=None, default=_MISSING):
    snapshot = _cache_get(key)
    if snapshot is None:
        try:
            snapshot = _load(key)
        except ParametroValueError:
            logger.error("Parametro %s con valor general invalido en BD.", key)
            snapshot = _UNDEFINED
        _cache_set(key, snapshot)
    if snapshot == _UNDEFINED:
        if default is _MISSING:
            raise LookupError(f"Parametro no definido: {key}")
        logger.warning("Parametro %s no definido o inactivo; se usa el default.", key)
        return default
    if center_id is not None and center_id in snapshot["centers"]:
        return snapshot["centers"][center_id]
    return snapshot["general"]


def invalidate(key):
    """Borra la cache DESPUES del commit: antes, un lector concurrente podria
    volver a cachear el valor viejo."""

    def _delete():
        try:
            cache.delete(_cache_key(key))
        except Exception:
            logger.warning("No se pudo invalidar la cache del parametro %s (expira sola).", key)

    transaction.on_commit(_delete)
