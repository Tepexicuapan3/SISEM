from django.db import models
from django.db.models import Q
from .base import CatalogBase


class Medicamentos(CatalogBase):
    """
    Catalogo de medicamentos individuales -- equivalente moderno de
    cat_medicamentos del legado (clave, nombre comercial/generico,
    presentacion, cuadro basico S/E/I, control de repeticion por no_caja).
    """

    class CuadroBasico(models.TextChoices):
        BASICO = "BASICO", "Cuadro Básico"
        ESPECIAL = "ESPECIAL", "Especial"
        INSTITUCIONAL = "INSTITUCIONAL", "Institucional"

    id = models.BigAutoField(primary_key=True, db_column="id_medic")
    # Clave del Compendio Nacional de Insumos (D2). Opcional hasta que farmacia
    # entregue el listado; unica entre las cargadas.
    code = models.CharField(max_length=30, db_column="cve_medic", null=True, blank=True)
    name = models.CharField(max_length=150, db_column="ds_medic")
    generic_name = models.CharField(
        max_length=150, db_column="ds_activo", null=True, blank=True,
    )
    presentation = models.CharField(
        max_length=150, db_column="presentacion", null=True, blank=True,
    )
    cuadro_basico = models.CharField(
        max_length=20,
        choices=CuadroBasico.choices,
        db_column="sw_cbasico",
        default=CuadroBasico.BASICO,
    )
    is_controlled = models.BooleanField(db_column="es_controlado", default=False)
    max_quantity = models.PositiveIntegerField(
        db_column="no_caja", null=True, blank=True,
    )

    @property
    def requires_prescription_authorization(self) -> bool:
        """Cuadro especial o controlado: la receta pide autorizacion antes de imprimirse."""
        return self.is_controlled or self.cuadro_basico == self.CuadroBasico.ESPECIAL

    class Meta:
        db_table = "cat_medicamentos"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(code__isnull=False) & ~Q(code=""),
                name="cat_medic_code_unique",
            ),
        ]
