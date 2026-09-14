# Catalogo de tipo de servicio/unidad de ambulancia -- reemplaza
# cat_serviciosa del legado. No hay catalogo de chofer/unidad fisica: el
# numero de unidad se captura como texto libre al autorizar (ver
# AmbulanceRequest.service_number).
from django.db import models
from .base import CatalogBase


class CatTipoServicioAmbulancia(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_tipo_servicio_ambulancia")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_tipo_servicio_ambulancia"
        managed = True
