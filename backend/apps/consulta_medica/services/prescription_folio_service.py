"""
Folio de receta (documento 5.3, cabecera RECETA).

Formato "RX-<anio>-<consecutivo de 6 digitos>", p. ej. "RX-2026-000123":
- Distinto del legado ("<clinica>R<aa>-<n>", genfolios.folioReceta): despues
  de la R el legado siempre pone el anio de 2 digitos o una F, asi que un
  folio de SIRES nunca se confunde con uno historico mientras convivan.
- Consecutivo por anio, como el legado, pero con la fila del contador
  bloqueada dentro de la transaccion (el legado reintentaba hasta 50 veces).
- No lleva datos del paciente.
"""
from django.db import transaction
from django.utils import timezone

from apps.consulta_medica.models import PrescriptionFolioCounter, VisitPrescription

FOLIO_PREFIX = "RX"


def format_folio(year, sequence):
    return f"{FOLIO_PREFIX}-{year}-{sequence:06d}"


def next_folio(year):
    """Siguiente (folio, consecutivo) del anio. Llamar dentro de una
    transaccion: el contador queda bloqueado hasta que termine."""
    with transaction.atomic():
        # get_or_create ya resuelve la carrera de dos altas del mismo anio.
        PrescriptionFolioCounter.objects.get_or_create(year=year)
        counter = PrescriptionFolioCounter.objects.select_for_update().get(year=year)
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
    return format_folio(year, counter.last_value), counter.last_value


def assign_folio(prescription):
    """Pone folio a una receta que no lo tiene. Escribe con update() para no
    re-serializar `items` (JSONField/jsonb, ver prescription_dispensation_repository)."""
    if prescription.folio:
        return prescription
    created = prescription.created_at or timezone.now()
    folio, sequence = next_folio(timezone.localtime(created).year)
    VisitPrescription.objects.filter(pk=prescription.pk, folio__isnull=True).update(
        folio=folio, sequence=sequence,
    )
    prescription.folio, prescription.sequence = folio, sequence
    return prescription
