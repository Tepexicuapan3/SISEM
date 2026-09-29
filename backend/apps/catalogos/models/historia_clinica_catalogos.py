"""
Catalogos de la historia clinica unificada (documento "Historia Clinica
Unificada", seccion 6 "Catalogos nuevos"). Se siembran por migracion
(`catalogos.0031`) porque la migracion de datos de `consulta_medica` los
necesita para mapear casillas/columnas del modelo anterior.
"""
from django.db import models

from .base import CatalogBase


class CatTipoAlergia(CatalogBase):
    """CAT_TIPO_ALERGIA del documento: 1 medicamento, 2 anestesia, 3 material
    dental, 4 ambiental, 5 alimento, 9 otro. El PK ES el codigo del documento
    (no autoincremental). `code` = clave estable para el cruce con recetas."""

    MEDICATION = 1

    id = models.PositiveSmallIntegerField(primary_key=True, db_column="cd_tipo_alergia")
    code = models.CharField(max_length=40, unique=True, db_column="clave")
    name = models.CharField(max_length=100, db_column="nombre")

    class Meta:
        db_table = "cat_tipo_alergia"
        managed = True
        ordering = ["id"]


class CatHabito(CatalogBase):
    """Tabaquismo, alcoholismo, toxicomanias, actividad fisica, alimentacion."""

    id = models.BigAutoField(primary_key=True, db_column="id_habito")
    code = models.CharField(max_length=40, unique=True, db_column="clave")
    name = models.CharField(max_length=100, db_column="nombre")

    class Meta:
        db_table = "cat_habito"
        managed = True
        ordering = ["name"]


class CatRegionCorporal(CatalogBase):
    """Regiones de la exploracion fisica (antes 6 columnas de his_clinica)."""

    id = models.BigAutoField(primary_key=True, db_column="id_region")
    code = models.CharField(max_length=40, unique=True, db_column="clave")
    name = models.CharField(max_length=100, db_column="nombre")
    order = models.PositiveSmallIntegerField(default=0, db_column="orden")

    class Meta:
        db_table = "cat_region_corporal"
        managed = True
        ordering = ["order", "name"]


class CatEstadoPieza(CatalogBase):
    """
    Estado de una pieza (o cara) dental en el odontograma. `code` conserva los
    valores que ya usaba `OdontogramTooth.condition` (contrato del frontend).
    `dmft_component` define como cuenta para el indice CPOD: C cariado,
    P perdido, O obturado, vacio = no cuenta. Valores iniciales sembrados como
    propuesta -- el documento deja la definicion final a estomatologia.
    """

    class DmftComponent(models.TextChoices):
        DECAYED = "C", "Cariado"
        MISSING = "P", "Perdido"
        FILLED = "O", "Obturado"

    id = models.BigAutoField(primary_key=True, db_column="id_estado_pieza")
    code = models.CharField(max_length=32, unique=True, db_column="clave")
    name = models.CharField(max_length=100, db_column="nombre")
    dmft_component = models.CharField(
        max_length=1, choices=DmftComponent.choices, null=True, blank=True, db_column="componente_cpod",
    )

    class Meta:
        db_table = "cat_estado_pieza"
        managed = True
        ordering = ["name"]


class CatPiezaDental(models.Model):
    """52 piezas en notacion FDI (ISO 3950). Catalogo fijo, no administrable."""

    class Dentition(models.TextChoices):
        PERMANENT = "P", "Permanente"
        DECIDUOUS = "T", "Temporal"

    fdi = models.CharField(primary_key=True, max_length=2, db_column="pieza_fdi")
    name = models.CharField(max_length=100, db_column="nombre")
    dentition = models.CharField(max_length=1, choices=Dentition.choices, db_column="tp_denticion")
    quadrant = models.PositiveSmallIntegerField(db_column="cuadrante")

    class Meta:
        db_table = "cat_pieza_dental"
        managed = True
        ordering = ["fdi"]
