"""
apps/folios/models.py
=========================
Consecutivos de folio por tipo de documento y anio. Unico dueno de la tabla;
los demas modulos piden folios con ``services.folio_service.next_folio``.
"""

from django.db import models


class FolioType(models.TextChoices):
    LICENCIA = "LIC", "Incapacidad"
    PASE = "REF", "Pase"
    AMBULANCIA = "AMB", "Solicitud de ambulancia"
    CIRUGIA = "CIR", "Cirugia programada"


class FolioCounter(models.Model):
    """Ultimo consecutivo emitido de un tipo en un anio. La fila se bloquea
    (SELECT ... FOR UPDATE) al asignar: dos altas simultaneas nunca reciben
    el mismo numero."""

    id = models.BigAutoField(primary_key=True, db_column="id_consecutivo")
    folio_type = models.CharField(max_length=10, db_column="tp_folio", choices=FolioType.choices)
    year = models.PositiveSmallIntegerField(db_column="anio")
    last_value = models.PositiveIntegerField(db_column="ultimo", default=0)

    class Meta:
        db_table = "fol_consecutivo"
        constraints = [
            models.UniqueConstraint(fields=["folio_type", "year"], name="fol_consecutivo_tipo_anio_uq"),
        ]

    def __str__(self) -> str:
        return f"{self.folio_type}-{self.year}: {self.last_value}"
