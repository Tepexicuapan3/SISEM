"""
apps/impresion/config.py
============================
Validacion de los settings propios del modulo. Vive aca (y no inline en
``config/settings.py``) para poder testear el caso invalido sin recargar el
modulo de settings.
"""

from django.core.exceptions import ImproperlyConfigured

FICHA_ENGINES = ("weasy", "docx")


def validate_ficha_engine(value):
    """Devuelve el motor normalizado o levanta ``ImproperlyConfigured``."""
    engine = str(value or "").strip().lower()
    if engine not in FICHA_ENGINES:
        raise ImproperlyConfigured(
            f"FICHA_ENGINE invalido: {value!r}. Valores permitidos: "
            f"{', '.join(FICHA_ENGINES)}"
        )
    return engine
