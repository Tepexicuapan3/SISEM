# Catalogo de clasificacion de cirugia (corta/quirofano/urgencia) -- reemplaza
# cat_tpcirugia del legado.
from django.db import models
from .base import CatalogBase


class CatClasificacionCirugia(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_clasificacion_cirugia")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_clasificacion_cirugia"
        managed = True
