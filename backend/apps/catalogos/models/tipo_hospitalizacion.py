# Catalogo de tipo de hospitalizacion -- reemplaza cat_tphospi del legado
# (java-main, dump Dump20260903.sql). Usado por hsp_admission.id_tipo_hospitalizacion
# (ver apps.hospitalizacion.models.HospitalAdmission).
from django.db import models

from .base import CatalogBase


class CatTipoHospitalizacion(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_tipo_hospitalizacion")
    name = models.CharField(max_length=200, db_column="nombre")
    # Clave de cat_tphospi en el legado. unique=True + null=True: Postgres/SQLite
    # tratan multiples NULL como distintos, asi que un tipo nativo de SIRES
    # (sin origen legado) convive sin colision -- mismo criterio que
    # CatMedico.legacy_cd_medico (apps/medicos/models.py:100).
    legacy_code = models.IntegerField(unique=True, null=True, blank=True, db_column="cd_legado")

    class Meta:
        db_table = "cat_tipo_hospitalizacion"
        managed = True
        ordering = ["name"]
