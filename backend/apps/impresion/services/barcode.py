"""
apps/impresion/services/barcode.py
======================================
Codigos de barras / QR como ``data:`` URI SVG (sin PIL ni cairo; el
``safe_fetcher`` permite ``data:``). Code128 reutiliza la codificacion de
reportlab (``decomposed``); QR usa ``qrcode`` con su fabrica SVG.
"""

import base64
from string import ascii_lowercase, ascii_uppercase
from xml.sax.saxutils import escape

from reportlab.graphics.barcode import code128


def _svg_data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def code128_data_uri(value, *, bar_width=1.0, bar_height=40.0):
    """Code128 de ``value`` como SVG data URI (unidades = ``bar_width``)."""
    value = str(value)
    if not value:
        raise ValueError("Valor vacio para codigo de barras")
    bc = code128.Code128(value, barWidth=bar_width, barHeight=bar_height, quiet=0)
    bc._calculate()  # llena bc.decomposed (mismo paso que Code128.draw)
    x = 0.0
    rects = []
    for c in bc.decomposed:
        if c in ascii_lowercase:
            x += (ord(c) - ord("a") + 1) * bar_width
        elif c in ascii_uppercase:
            w = (ord(c) - ord("A") + 1) * bar_width
            rects.append(f'<rect x="{x:g}" y="0" width="{w:g}" height="{bar_height:g}"/>')
            x += w
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{x:g}" height="{bar_height:g}" '
        f'viewBox="0 0 {x:g} {bar_height:g}" aria-label="{escape(value)}" '
        f'shape-rendering="crispEdges"><g fill="#000">{"".join(rects)}</g></svg>'
    )
    return _svg_data_uri(svg)


def qr_data_uri(value):
    """QR de ``value`` como SVG data URI."""
    import io

    import qrcode
    import qrcode.image.svg

    img = qrcode.make(str(value), image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return _svg_data_uri(buf.getvalue().decode("utf-8"))
