from django.db import models

from apps.catalogos.models.base import CatalogBase

from .catalogos import Almacen, CatInsumo, CatProveedor


class LoteInsumo(models.Model):
    id_lote         = models.BigAutoField(primary_key=True, db_column="id_lote")
    id_insumo       = models.ForeignKey(CatInsumo,   on_delete=models.PROTECT, related_name="lotes",    db_column="id_insumo")
    id_proveedor    = models.ForeignKey(CatProveedor, on_delete=models.PROTECT, related_name="lotes",    db_column="id_proveedor", null=True, blank=True)
    num_lote        = models.CharField(max_length=100)
    fecha_caducidad = models.DateField(null=True, blank=True)
    fch_alta        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = "almacen_lotes_insumo"
        unique_together = [("id_insumo", "num_lote")]
        ordering        = ["-fch_alta"]

    def __str__(self) -> str:
        return f"{self.id_insumo} — {self.num_lote}"


class EntradaInventario(CatalogBase):
    id_entrada   = models.BigAutoField(primary_key=True, db_column="id_entrada")
    id_almacen   = models.ForeignKey(Almacen,     on_delete=models.PROTECT, related_name="entradas",   db_column="id_almacen")
    id_proveedor = models.ForeignKey(CatProveedor, on_delete=models.PROTECT, related_name="entradas",   db_column="id_proveedor", null=True, blank=True)
    num_remision = models.CharField(max_length=120, blank=True, default="")
    fch_entrada  = models.DateField()
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        db_table = "almacen_entradas_inventario"
        ordering = ["-fch_entrada", "-created_at"]

    def __str__(self) -> str:
        return f"Entrada {self.pk} — {self.id_almacen} ({self.fch_entrada})"


class EntradaInventarioDetail(models.Model):
    id_entrada_det = models.BigAutoField(primary_key=True, db_column="id_entrada_det")
    id_entrada     = models.ForeignKey(EntradaInventario, on_delete=models.CASCADE, related_name="detalles", db_column="id_entrada")
    id_insumo      = models.ForeignKey(CatInsumo,          on_delete=models.PROTECT, related_name="entradas_det", db_column="id_insumo")
    id_lote        = models.ForeignKey(LoteInsumo,         on_delete=models.PROTECT, related_name="entradas_det", db_column="id_lote", null=True, blank=True)
    cantidad       = models.DecimalField(max_digits=14, decimal_places=4)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        db_table = "almacen_entradas_inventario_det"

    def __str__(self) -> str:
        return f"Det entrada {self.id_entrada_id} — {self.id_insumo}"


class KardexMovimiento(models.Model):
    class TipoMovimiento(models.TextChoices):
        ENTRADA          = "ENTRADA",          "Entrada"
        SALIDA           = "SALIDA",           "Salida"
        DEVOLUCION       = "DEVOLUCION",       "Devolución"
        MERMA            = "MERMA",            "Merma"
        AJUSTE_POSITIVO  = "AJUSTE_POSITIVO",  "Ajuste positivo"
        AJUSTE_NEGATIVO  = "AJUSTE_NEGATIVO",  "Ajuste negativo"
        CONSUMO          = "CONSUMO",          "Consumo consulta"

    id_movimiento     = models.BigAutoField(primary_key=True, db_column="id_movimiento")
    id_insumo         = models.ForeignKey(CatInsumo,  on_delete=models.PROTECT, related_name="kardex",  db_column="id_insumo")
    id_lote           = models.ForeignKey(LoteInsumo, on_delete=models.PROTECT, related_name="kardex",  db_column="id_lote", null=True, blank=True)
    id_almacen        = models.ForeignKey(Almacen,    on_delete=models.PROTECT, related_name="kardex",  db_column="id_almacen")
    tipo_movimiento   = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    cantidad          = models.DecimalField(max_digits=14, decimal_places=4)
    saldo_resultante  = models.DecimalField(max_digits=14, decimal_places=4)
    ref_modelo        = models.CharField(max_length=100)
    ref_id            = models.BigIntegerField()
    fch_movimiento    = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by_id     = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "almacen_kardex_movimientos"
        indexes  = [
            models.Index(fields=["id_insumo", "id_almacen", "fch_movimiento"], name="kardex_insumo_alm_fch_idx"),
            models.Index(fields=["id_lote",   "fch_movimiento"],               name="kardex_lote_fch_idx"),
        ]
        ordering = ["-fch_movimiento"]

    def __str__(self) -> str:
        return f"{self.tipo_movimiento} {self.id_insumo} — {self.cantidad} (saldo: {self.saldo_resultante})"


class ExistenciaAlmacen(models.Model):
    id_existencia = models.BigAutoField(primary_key=True, db_column="id_existencia")
    id_insumo  = models.ForeignKey(CatInsumo,  on_delete=models.PROTECT, related_name="existencias", db_column="id_insumo")
    id_lote    = models.ForeignKey(LoteInsumo, on_delete=models.PROTECT, related_name="existencias", db_column="id_lote", null=True, blank=True)
    id_almacen = models.ForeignKey(Almacen,    on_delete=models.PROTECT, related_name="existencias", db_column="id_almacen")
    cantidad   = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        db_table        = "almacen_existencias"
        unique_together = [("id_insumo", "id_lote", "id_almacen")]

    def __str__(self) -> str:
        return f"Existencia {self.id_insumo} | lote={self.id_lote_id} | alm={self.id_almacen_id} = {self.cantidad}"


# ─── Phase 3: Salidas ────────────────────────────────────────────────────────

class SalidaInventario(CatalogBase):
    class TipoSalida(models.TextChoices):
        SALIDA     = "SALIDA",     "Salida directa"
        MERMA      = "MERMA",      "Merma / Pérdida"
        DEVOLUCION = "DEVOLUCION", "Devolución a proveedor"

    id_salida   = models.BigAutoField(primary_key=True, db_column="id_salida")
    id_almacen  = models.ForeignKey(Almacen,  on_delete=models.PROTECT, related_name="salidas",    db_column="id_almacen")
    tipo_salida = models.CharField(max_length=20, choices=TipoSalida.choices, default=TipoSalida.SALIDA)
    num_folio   = models.CharField(max_length=120, blank=True, default="")
    fch_salida  = models.DateField()
    motivo      = models.TextField(blank=True, default="")

    class Meta:
        db_table = "almacen_salidas_inventario"
        ordering = ["-fch_salida", "-created_at"]

    def __str__(self) -> str:
        return f"Salida {self.pk} — {self.id_almacen} ({self.tipo_salida})"


class SalidaInventarioDetail(models.Model):
    id_salida_det = models.BigAutoField(primary_key=True, db_column="id_salida_det")
    id_salida = models.ForeignKey(SalidaInventario, on_delete=models.CASCADE, related_name="detalles",    db_column="id_salida")
    id_insumo = models.ForeignKey(CatInsumo,        on_delete=models.PROTECT, related_name="salidas_det", db_column="id_insumo")
    id_lote   = models.ForeignKey(LoteInsumo,       on_delete=models.PROTECT, related_name="salidas_det", db_column="id_lote",   null=True, blank=True)
    cantidad  = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        db_table = "almacen_salidas_inventario_det"

    def __str__(self) -> str:
        return f"Det salida {self.id_salida_id} — {self.id_insumo}"


# ─── Phase 4: Conteo Físico ──────────────────────────────────────────────────

class ConteoFisico(CatalogBase):
    id_conteo     = models.BigAutoField(primary_key=True, db_column="id_conteo")
    id_almacen    = models.ForeignKey(Almacen, on_delete=models.PROTECT, related_name="conteos",   db_column="id_almacen")
    fch_conteo    = models.DateField()
    observaciones = models.TextField(blank=True, default="")
    cerrado       = models.BooleanField(default=False)
    fch_cierre    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "almacen_conteos_fisicos"
        ordering = ["-fch_conteo", "-created_at"]

    def __str__(self) -> str:
        return f"Conteo {self.pk} — {self.id_almacen} ({self.fch_conteo})"


class ConteoFisicoDetalle(models.Model):
    id_conteo_det = models.BigAutoField(primary_key=True, db_column="id_conteo_det")
    id_conteo    = models.ForeignKey(ConteoFisico, on_delete=models.CASCADE, related_name="detalles",   db_column="id_conteo")
    id_insumo    = models.ForeignKey(CatInsumo,    on_delete=models.PROTECT, related_name="conteos_det", db_column="id_insumo")
    id_lote      = models.ForeignKey(LoteInsumo,   on_delete=models.PROTECT, related_name="conteos_det", db_column="id_lote",    null=True, blank=True)
    cant_sistema = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    cant_fisica  = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        db_table        = "almacen_conteos_fisicos_det"
        unique_together = [("id_conteo", "id_insumo", "id_lote")]

    def __str__(self) -> str:
        return f"Det conteo {self.id_conteo_id} — {self.id_insumo}"


# ─── Phase 6: Consumos por Consulta ─────────────────────────────────────────

class ConsumoConsulta(CatalogBase):
    id_consumo    = models.BigAutoField(primary_key=True, db_column="id_consumo")
    id_almacen    = models.ForeignKey(Almacen, on_delete=models.PROTECT, related_name="consumos",  db_column="id_almacen")
    id_cita       = models.BigIntegerField(null=True, blank=True, db_index=True)
    paciente      = models.CharField(max_length=200, blank=True, default="")
    medico        = models.ForeignKey(
        "medicos.CatMedico",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="consumos_insumos",
    )
    fch_consumo   = models.DateField()
    observaciones = models.TextField(blank=True, default="")

    class Meta:
        db_table = "almacen_consumos_consulta"
        ordering = ["-fch_consumo", "-created_at"]

    def __str__(self) -> str:
        return f"Consumo {self.pk} — {self.id_almacen} ({self.fch_consumo})"


class ConsumoConsultaDetalle(models.Model):
    id_consumo_det = models.BigAutoField(primary_key=True, db_column="id_consumo_det")
    id_consumo = models.ForeignKey(ConsumoConsulta, on_delete=models.CASCADE, related_name="detalles",    db_column="id_consumo")
    id_insumo  = models.ForeignKey(CatInsumo,       on_delete=models.PROTECT, related_name="consumos_det", db_column="id_insumo")
    id_lote    = models.ForeignKey(LoteInsumo,      on_delete=models.PROTECT, related_name="consumos_det", db_column="id_lote",    null=True, blank=True)
    cantidad   = models.DecimalField(max_digits=14, decimal_places=4)
    # Enlace opcional a la dispensacion de farmacia (sdd/dispensacion-farmacia).
    # FK cross-app por STRING a proposito: cero import en tiempo de modulo de
    # `consulta_medica` desde `almacen_insumos` (ver design seccion d). Se
    # permiten multiples eventos parciales por item de receta -- NO llevar
    # UniqueConstraint aca, seria incompatible con dispensacion parcial.
    prescription_item = models.ForeignKey(
        "consulta_medica.VisitPrescriptionItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_receta_item",
        related_name="consumo_detalles",
    )

    class Meta:
        db_table = "almacen_consumos_consulta_det"

    def __str__(self) -> str:
        return f"Det consumo {self.id_consumo_id} — {self.id_insumo}"
