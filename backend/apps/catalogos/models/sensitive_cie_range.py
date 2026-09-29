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

    class Level(models.TextChoices):
        # CAT_DATO_SENSIBLE.nivel (documento): R restringido, C confidencial.
        RESTRICTED = "R", "Restringido"
        CONFIDENTIAL = "C", "Confidencial"

    level = models.CharField(max_length=1, db_column="nivel", choices=Level.choices, default=Level.RESTRICTED)

    class Meta:
        db_table = "cat_rango_cie_sensible"
        managed = True
        ordering = ["code_prefix_start"]

    def __str__(self):
        return f"{self.code_prefix_start}-{self.code_prefix_end} ({self.category})"


class SensitiveAccessProfile(models.Model):
    """
    CAT_PERFIL_ACCESO (documento: CAT_DATO_SENSIBLE }o--o{ CAT_PERFIL_ACCESO
    "visible para"): que perfiles ven un dato sensible sin redaccion. En SIRES
    los perfiles son los roles (`cat_roles`). Un usuario ve el diagnostico si
    tiene el permiso del rango (`required_permission`) O si alguno de sus
    roles esta aqui para ese rango. Se administra con el comando
    `python manage.py perfil_acceso_sensible`.
    """

    id = models.BigAutoField(primary_key=True, db_column="id_perfil_acceso")
    sensitive_range = models.ForeignKey(
        SensitiveCieRange, db_column="id_rango_sensible", on_delete=models.CASCADE,
        related_name="access_profiles",
    )
    role = models.ForeignKey(
        "catalogos.Roles", db_column="id_rol", on_delete=models.CASCADE, related_name="+",
    )
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cat_perfil_acceso_sensible"
        managed = True
        constraints = [
            models.UniqueConstraint(fields=["sensitive_range", "role"], name="cat_perfil_acceso_uniq"),
        ]
