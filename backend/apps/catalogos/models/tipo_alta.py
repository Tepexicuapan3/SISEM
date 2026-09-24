# Catalogo de tipo de alta hospitalaria -- reemplaza cat_tpaltas del legado
# (java-main, dump Dump20260903.sql). Usado por hsp_admission.id_tipo_alta
# (ver apps.hospitalizacion.models.HospitalAdmission).
from django.db import models

from .base import CatalogBase


class CatTipoAlta(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_tipo_alta")
    name = models.CharField(max_length=200, db_column="nombre")
    # Clave de cat_tpaltas en el legado. unique=True + null=True: mismo
    # criterio que CatTipoHospitalizacion.legacy_code.
    legacy_code = models.IntegerField(unique=True, null=True, blank=True, db_column="cd_legado")

    class Meta:
        db_table = "cat_tipo_alta"
        managed = True
        ordering = ["name"]
