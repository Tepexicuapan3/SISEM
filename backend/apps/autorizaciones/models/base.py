"""Columnas de trazabilidad comunes a las tablas del modulo de autorizaciones.

Equivalen a las de `catalogos.CatalogBase` (est_activo, fch_alta, usr_alta...),
pero con nombres completos en espanol para que la tabla se lea sola en
PostgreSQL. Nunca hay DELETE fisico: la baja es `fecha_baja` + `esta_activo`.
"""
from django.db import models


class RegistroAuditable(models.Model):
    esta_activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(null=True, blank=True)
    fecha_baja = models.DateTimeField(null=True, blank=True)
    id_usuario_creacion = models.BigIntegerField(null=True, blank=True)
    id_usuario_modificacion = models.BigIntegerField(null=True, blank=True)
    id_usuario_baja = models.BigIntegerField(null=True, blank=True)

    class Meta:
        abstract = True
