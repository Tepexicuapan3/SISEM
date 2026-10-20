"""
Folio de documentos clinicos: "<PREFIJO>-<anio>-<consecutivo de 6 digitos>",
p. ej. "LIC-2026-000123". Mismo criterio que la receta
(consulta_medica/services/prescription_folio_service):

- Consecutivo por tipo y anio con la fila del contador bloqueada.
- No lleva datos del paciente (el formato anterior llevaba el expediente y
  la hora al segundo: dos documentos del mismo paciente en el mismo segundo
  chocaban contra el unique y terminaban en 500).
- Los folios ya emitidos con el formato anterior no se tocan.

Llamar DENTRO de la transaccion que crea el documento: si el alta falla, el
consecutivo se revierte con ella y no quedan huecos.
"""

from django.db import transaction
from django.utils import timezone

from apps.folios.models import FolioCounter, FolioType


def format_folio(folio_type, year, sequence):
    return f"{FolioType(folio_type).value}-{year}-{sequence:06d}"


def next_folio(folio_type, *, when=None):
    """Siguiente folio del tipo en el anio de ``when`` (hora local; default ahora)."""
    folio_type = FolioType(folio_type)
    year = timezone.localtime(when or timezone.now()).year
    with transaction.atomic():
        # get_or_create ya resuelve la carrera de dos altas del mismo anio.
        FolioCounter.objects.get_or_create(folio_type=folio_type, year=year)
        counter = FolioCounter.objects.select_for_update().get(folio_type=folio_type, year=year)
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
    return format_folio(folio_type, year, counter.last_value)
