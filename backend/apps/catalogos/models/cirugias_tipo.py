# Catalogo de tipo/paquete de cirugia -- reemplaza cat_cirugias del legado
# (java-main/investigacion/consolidado_assets/sisem/usuarios/clinicam).
from django.db import models
from .base import CatalogBase


class CatTipoCirugia(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_tipo_cirugia")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_tipo_cirugia"
        managed = True
