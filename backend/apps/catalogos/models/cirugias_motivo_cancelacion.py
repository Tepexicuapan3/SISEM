# Catalogo de motivo de cancelacion de cirugia. No existia como catalogo
# independiente en el legado (det_cancelaqx solo guardaba texto libre en
# ds_motivo); se tipifica aqui para reportabilidad.
from django.db import models
from .base import CatalogBase


class CatMotivoCancelacionCirugia(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_motivo_cancelacion_cirugia")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_motivo_cancelacion_cirugia"
        managed = True
