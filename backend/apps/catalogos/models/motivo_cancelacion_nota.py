# Catalogo de motivos de cancelacion de nota de consulta (change
# cancelacion-nota-cascada). Mismo patron que cirugias_motivo_cancelacion.py.
# Es DISTINTO de MotivoCita (motivo de cancelacion de la VISITA en recepcion).
from django.db import models
from .base import CatalogBase


class MotivoCancelacionNota(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_motivo_cancelacion_nota")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_motivo_cancelacion_nota"
        managed = True
