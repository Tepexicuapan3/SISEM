from django.core.validators import RegexValidator
from django.db import models

from .base import CatalogBase


class CatCentroAtencion(CatalogBase):

    class TipoCentro(models.TextChoices):
        CLINICA   = "CLINICA",   "Clínica"
        HOSPITAL  = "HOSPITAL",  "Hospital"
        INSTITUTO = "INSTITUTO", "Instituto"

    id          = models.BigAutoField(primary_key=True, db_column="id_centro_atencion")
    name        = models.CharField(max_length=120, db_column="nombre")
    code        = models.CharField(max_length=50, unique=True, db_column="clues")
    center_type = models.CharField(
        max_length=20,
        choices=TipoCentro.choices,
        db_column="tipo_centro",
        db_index=True,          # útil si filtras por tipo
    )
    legacy_folio = models.CharField(max_length=10, null=True, blank=True, db_column="folio_clin")
    # Puente cd_clinica (legado his_hospital.cd_origeno) -> este centro.
    # legacy_folio ya guarda cat_clinicas.ds_folio (varchar(2)); ninguno de
    # los campos existentes guarda el INT cd_clinica que usa his_hospital,
    # de ahi este campo nuevo (change his-hospital-modelo-nom024, migracion
    # 0029). Sin unique=True: ~14 clinicas, pero un indice unico sobre una
    # tabla managed=False con posible drift en produccion es riesgo
    # innecesario -- db_index alcanza para el JOIN; la unicidad se valida
    # en el seed/carga manual.
    legacy_cd_clinica = models.IntegerField(
        null=True, blank=True, db_column="cd_clinica_legado", db_index=True,
    )
    is_external  = models.BooleanField(default=False, db_column="es_externo")

    # Dirección
    address      = models.CharField(max_length=255, null=True, blank=True, db_column="direccion")
    postal_code  = models.CharField(
        max_length=5,
        null=True,
        blank=True,
        db_column="codigo_postal",
        validators=[RegexValidator(r"^\d{5}$", "El código postal debe tener exactamente 5 dígitos.")],
    )
    neighborhood = models.CharField(max_length=120, null=True, blank=True, db_column="colonia")
    municipality = models.CharField(max_length=120, null=True, blank=True, db_column="municipio")
    state        = models.CharField(max_length=120, null=True, blank=True, db_column="estado")
    city         = models.CharField(max_length=120, null=True, blank=True, db_column="ciudad")
    phone        = models.CharField(max_length=40,  null=True, blank=True, db_column="telefono")

    class Meta:
        db_table      = "cat_centros_atencion"
        managed       = False
        ordering      = ["name"]
        verbose_name  = "Centro de Atención"
        verbose_name_plural = "Centros de Atención"

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"