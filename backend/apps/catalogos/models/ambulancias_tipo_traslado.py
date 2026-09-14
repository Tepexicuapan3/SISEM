# Catalogo de tipo de traslado en ambulancia -- reemplaza cat_traslados del legado.
from django.db import models
from .base import CatalogBase


class CatTipoTraslado(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_tipo_traslado")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_tipo_traslado"
        managed = True
