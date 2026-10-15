"""
apps/impresion/engine.py
============================
Motor de PDF (WeasyPrint). El import de ``weasyprint`` es perezoso: en
Windows de desarrollo sin GTK/Pango el proyecto y los tests de builders
siguen importando sin problema.
"""

import logging

from django.template.loader import render_to_string

from apps.impresion.errors import PrintError
from apps.impresion.services.safe_fetcher import ASSETS_DIR, safe_fetcher

logger = logging.getLogger(__name__)


def render_pdf(template, context):
    """Renderiza ``template`` con ``context`` y devuelve los bytes del PDF.

    Cualquier fallo (libs nativas ausentes, plantilla, layout) se traduce a
    ``PrintError(PRINT_RENDER_ERROR, 500)`` con mensaje generico.
    """
    try:
        import weasyprint  # import perezoso

        html = render_to_string(template, context)
        return weasyprint.HTML(
            string=html,
            base_url=str(ASSETS_DIR),
            url_fetcher=safe_fetcher,
        ).write_pdf()
    except Exception as exc:
        logger.exception("Fallo el render PDF de %s", template)
        raise PrintError(
            code="PRINT_RENDER_ERROR",
            message="No se pudo generar el documento",
            status_code=500,
        ) from exc
