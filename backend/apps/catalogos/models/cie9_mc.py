# NOM-024-SSA3: catalogo de procedimientos CIE-9-MC, complementario a CIE-10
# (CatCies, ver cies.py) que solo cubre diagnosticos. Mismo patron que
# Discapacidades/Escuelas (id surrogado + code + name) para reutilizar tal cual
# el pipeline generico de import masivo (CATALOG_IMPORT_REGISTRY).
from django.db import models
from .base import CatalogBase


class CatCie9Mc(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_cie9_mc")
    code = models.CharField(max_length=10, db_column="clave_cie9_mc")
    name = models.CharField(max_length=400, db_column="descripcion_cie9_mc")

    class Meta:
        db_table = "cat_cie9_mc"
        managed = True
        constraints = [
            models.UniqueConstraint(fields=["code"], name="cat_cie9_mc_codigo_uniq"),
        ]
