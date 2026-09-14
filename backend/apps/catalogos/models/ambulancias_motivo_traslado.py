# Catalogo de motivo de traslado en ambulancia -- reemplaza cat_motivosamb
# del legado. Uno de los valores (equivalente al "Otro" del legado) requiere
# texto libre adicional -- ver AmbulanceRequest.reason_notes.
from django.db import models
from .base import CatalogBase


class CatMotivoTraslado(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_motivo_traslado")
    name = models.CharField(max_length=200, db_column="nombre")
    requires_notes = models.BooleanField(
        default=False,
        db_column="requiere_notas",
        help_text="Si es verdadero, la solicitud exige texto libre en reason_notes (equivalente al motivo 'Otro' del legado).",
    )

    class Meta:
        db_table = "cat_motivo_traslado"
        managed = True
