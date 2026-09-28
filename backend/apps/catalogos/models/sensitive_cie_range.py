from django.db import models

from .base import CatalogBase


class SensitiveCieRange(CatalogBase):
    """
    Rango de codigos CIE-10 clasificados como sensibles (VIH, salud mental,
    consumo de sustancias) -- change `diagnosticos-sensibles`. Tabla
    configurable (no hardcodeada en Python) para que control de
    calidad/juridico pueda ajustar los rangos sin desplegar codigo nuevo,
    mismo criterio que el resto de catalogos de SISEM.

    `code_prefix_start`/`code_prefix_end` son codigos de CATEGORIA de 3
    caracteres (letra + 2 digitos, ej. "B20", "F19" -- SIN el punto
    decimal). `sensitive_diagnosis_service.classify_cie` compara solo el
    prefijo de 3 caracteres de `catalogos.CatCies.code` contra estos
    limites (nunca el codigo completo con decimales), porque los bloques
    CIE-10 se definen por categoria: "B20-B24" incluye TODOS los subcodigos
    B20.0..B24.9.

    Ver `PatientAllergiesView`/`Allergy` (change `alergias-unificadas`) para
    el patron hermano de "tabla catalogo chica que dispara logica de
    proteccion" -- aca el disparador es `required_permission`, evaluado via
    `evaluate_permission_requirement` en
    `consulta_medica.services.diagnosis_redaction_service`.
    """

    class Category(models.TextChoices):
        HIV = "hiv", "VIH"
        MENTAL_HEALTH = "mental_health", "Salud mental"
        SUBSTANCE_USE = "substance_use", "Consumo de sustancias"

    id = models.BigAutoField(primary_key=True, db_column="id_rango_sensible")
    code_prefix_start = models.CharField(max_length=8, db_column="codigo_inicio")
    code_prefix_end = models.CharField(max_length=8, db_column="codigo_fin")
    category = models.CharField(
        max_length=20, choices=Category.choices, db_column="categoria",
    )
    # Codigo de `catalogos.Permisos` (namespaced, ej.
    # "clinico:diagnosticos_vih:read") -- CharField en vez de FK real a
    # Permisos porque los permisos de SISEM se referencian por codigo string
    # en todo el sistema (ver `evaluate_permission_requirement`), no por FK.
    required_permission = models.CharField(max_length=100, db_column="permiso_requerido")

    class Meta:
        db_table = "cat_rango_cie_sensible"
        managed = True
        ordering = ["code_prefix_start"]

    def __str__(self):
        return f"{self.code_prefix_start}-{self.code_prefix_end} ({self.category})"
