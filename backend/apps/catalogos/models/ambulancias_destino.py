# Catalogo de destinos de traslado en ambulancia -- reemplaza
# cat_dest_ambulancia del legado. Es traslado INTERNO entre unidades propias
# de la institucion (no ambulancia de emergencia externa), por eso el destino
# siempre se normaliza contra este catalogo en vez de recapturar texto libre
# por solicitud.
from django.db import models
from .base import CatalogBase


class CatDestinoAmbulancia(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_destino_ambulancia")
    name = models.CharField(max_length=200, db_column="nombre")
    street = models.CharField(max_length=200, null=True, blank=True, db_column="calle")
    zip_code = models.CharField(max_length=10, null=True, blank=True, db_column="codigo_postal")
    neighborhood = models.CharField(max_length=150, null=True, blank=True, db_column="colonia")
    borough = models.CharField(max_length=150, null=True, blank=True, db_column="delegacion")
    phone = models.CharField(max_length=40, null=True, blank=True, db_column="telefono")
    reference = models.TextField(null=True, blank=True, db_column="referencia")

    class Meta:
        db_table = "cat_destino_ambulancia"
        managed = True
