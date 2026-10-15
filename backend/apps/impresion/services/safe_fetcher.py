"""
apps/impresion/services/safe_fetcher.py
===========================================
``url_fetcher`` de WeasyPrint que solo permite recursos locales dentro de
``static/impresion`` (y ``data:`` URIs inline, p. ej. codigos de barras).
Bloquea http(s)/ftp y cualquier ``file://`` fuera del directorio: evita SSRF
y lectura de archivos arbitrarios desde plantillas con datos de usuario.
"""

from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

ASSETS_DIR = Path(__file__).resolve().parent.parent / "static" / "impresion"


class BlockedUrlError(ValueError):
    pass


def is_allowed_url(url, assets_dir=ASSETS_DIR):
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme == "data":
        return True
    if scheme != "file" or parsed.netloc not in ("", "localhost"):
        return False
    path = Path(url2pathname(unquote(parsed.path))).resolve()
    return path.is_relative_to(Path(assets_dir).resolve())


def safe_fetcher(url, *args, **kwargs):
    if not is_allowed_url(url):
        raise BlockedUrlError(f"Recurso no permitido: {url}")
    from weasyprint import default_url_fetcher  # import perezoso

    return default_url_fetcher(url, *args, **kwargs)
