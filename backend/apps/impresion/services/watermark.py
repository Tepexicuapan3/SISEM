"""
apps/impresion/services/watermark.py
========================================
Decision pura de marcas de agua. CANCELADA tiene prioridad (va primero) y
REIMPRESION se agrega ademas cuando aplica (copia > 1 y el documento la
solicita: ``DocumentSpec.watermark_on_reprint``; la ficha no).
"""

from dataclasses import dataclass

CANCELADA = "CANCELADA"
REIMPRESION = "REIMPRESIÓN"


@dataclass(frozen=True)
class Watermark:
    label: str
    css: str


def resolve_watermarks(*, is_cancelled, copy_number, watermark_on_reprint=True):
    marks = []
    if is_cancelled:
        marks.append(Watermark(CANCELADA, "cancelada"))
    if copy_number > 1 and watermark_on_reprint:
        marks.append(Watermark(REIMPRESION, "reimpresion"))
    return marks
