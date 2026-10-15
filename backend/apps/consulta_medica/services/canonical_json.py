"""JSON canonico + SHA-256 para el snapshot de cancelacion de nota.

Change cancelacion-nota-cascada. El snapshot se guarda como TEXTO (no JSONField)
porque json/jsonb reordenan y normalizan: el hash solo es verificable si se
conserva la serializacion byte a byte.

Reglas de normalizacion (v1):
  - dict con claves ordenadas, separadores compactos, UTF-8 sin escapar;
  - Decimal -> string en notacion fija ("1.50");
  - date -> "YYYY-MM-DD";
  - datetime -> UTC "YYYY-MM-DDTHH:MM:SS.ffffffZ" (naive se asume UTC);
  - None -> null; tuplas/sets de listas se serializan como listas (el caller
    ordena las listas por id: aqui no se reordena nada).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

SCHEMA = "cancelacion-nota/v1"


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        # Los floats no tienen representacion canonica estable entre
        # plataformas: el caller debe pasar Decimal o string.
        raise TypeError("canonical_json no admite float: usa Decimal o str.")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    raise TypeError(f"canonical_json: tipo no soportado {type(value).__name__}.")


def canonical_json(obj: Any) -> str:
    """Serializacion canonica determinista (mismo contenido -> mismo texto)."""
    return json.dumps(
        _normalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )


def canonical_bytes(obj: Any) -> bytes:
    return canonical_json(obj).encode("utf-8")


def sha256_hex(content: str | bytes) -> str:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()
