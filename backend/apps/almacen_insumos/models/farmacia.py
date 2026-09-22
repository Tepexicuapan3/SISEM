from django.db import models
from django.db.models import Q

from apps.catalogos.models.base import CatalogBase

from .catalogos import CatInsumo


class MedicamentoInsumo(CatalogBase):
    """
    Mapeo manual `Medicamento` (catalogos, recetado por el medico) ->
    `CatInsumo` (almacen_insumos, con existencias reales) -- puente entre
    Autorizacion de Recetas y el kardex de farmacia. Ver
    `sdd/dispensacion-farmacia/design` seccion (d).

    Un solo mapeo ACTIVO por medicamento (UniqueConstraint condicionada),
    igual criterio que `cns_rxitem_one_active_per_medication` en
    `VisitPrescriptionItem`. `factor_conversion` convierte la cantidad
    prescrita (unidades de medicamento, sin unidad explicita) a la
    cantidad real de insumo a descontar del kardex.
    """

    id_medicamento_insumo = models.BigAutoField(
        primary_key=True, db_column="id_medicamento_insumo",
    )
    medicamento = models.ForeignKey(
        "catalogos.Medicamentos",
        on_delete=models.PROTECT,
        db_column="id_medic",
        related_name="insumo_mapeos",
    )
    insumo = models.ForeignKey(
        CatInsumo,
        on_delete=models.PROTECT,
        db_column="id_insumo",
        related_name="medicamento_mapeos",
    )
    factor_conversion = models.DecimalField(
        max_digits=12, decimal_places=4, default=1,
    )
    permite_fraccion = models.BooleanField(default=True)

    class Meta:
        db_table = "almacen_medicamento_insumo"
        constraints = [
            models.UniqueConstraint(
                fields=["medicamento"],
                condition=Q(is_active=True),
                name="almacen_medins_one_active_per_medic",
            ),
            models.CheckConstraint(
                condition=Q(factor_conversion__gt=0),
                name="almacen_medins_factor_positivo",
            ),
        ]
        verbose_name = "Mapeo Medicamento-Insumo"
        verbose_name_plural = "Mapeos Medicamento-Insumo"

    def __str__(self) -> str:
        return f"{self.medicamento_id} -> {self.insumo_id} (x{self.factor_conversion})"
