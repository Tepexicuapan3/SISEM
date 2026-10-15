"""
apps/impresion/services/branding.py
=======================================
Logo por centro: ``static/impresion/logos/{legacy_cd_clinica}a.gif`` con
fallback al logo generico. Devuelve ``file://`` URI (el url_fetcher solo
permite recursos dentro de ``static/impresion``).
"""

from apps.impresion.services.safe_fetcher import ASSETS_DIR

LOGOS_DIR = ASSETS_DIR / "logos"
DEFAULT_LOGO = LOGOS_DIR / "default.svg"


def resolve_logo_uri(legacy_cd_clinica, logos_dir=LOGOS_DIR, default=DEFAULT_LOGO):
    if legacy_cd_clinica is not None:
        candidate = logos_dir / f"{int(legacy_cd_clinica)}a.gif"
        if candidate.is_file():
            return candidate.resolve().as_uri()
    return default.resolve().as_uri()
