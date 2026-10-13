from rest_framework import serializers

from apps.medicos.identity import annotate_display_name, display_name, with_identity
from apps.medicos.models import CatMedico
from apps.almacen_insumos.models.kardex import (
    ConteoFisico,
    ConteoFisicoDetalle,
    ConsumoConsulta,
    ConsumoConsultaDetalle,
    EntradaInventario,
    EntradaInventarioDetail,
    ExistenciaAlmacen,
    KardexMovimiento,
    LoteInsumo,
    SalidaInventario,
    SalidaInventarioDetail,
)


class LoteInsumoSerializer(serializers.ModelSerializer):
    id            = serializers.IntegerField(source="pk", read_only=True)
    idInsumo      = serializers.PrimaryKeyRelatedField(source="id_insumo",    read_only=True)
    insumoNombre  = serializers.CharField(source="id_insumo.nombre",          read_only=True)
    idProveedor   = serializers.PrimaryKeyRelatedField(source="id_proveedor", read_only=True)
    numLote       = serializers.CharField(source="num_lote")
    fechaCaducidad = serializers.DateField(source="fecha_caducidad", allow_null=True, required=False)
    fchAlta       = serializers.DateTimeField(source="fch_alta", read_only=True)

    class Meta:
        model  = LoteInsumo
        fields = ["id", "idInsumo", "insumoNombre", "idProveedor", "numLote", "fechaCaducidad", "fchAlta"]


class LoteInsumoCreateSerializer(serializers.ModelSerializer):
    idInsumo       = serializers.IntegerField(source="id_insumo_id")
    idProveedor    = serializers.IntegerField(source="id_proveedor_id", required=False, allow_null=True)
    numLote        = serializers.CharField(source="num_lote", max_length=100)
    fechaCaducidad = serializers.DateField(source="fecha_caducidad", required=False, allow_null=True)

    class Meta:
        model  = LoteInsumo
        fields = ["idInsumo", "idProveedor", "numLote", "fechaCaducidad"]


class EntradaDetalleSerializer(serializers.ModelSerializer):
    id            = serializers.IntegerField(source="pk", read_only=True)
    idInsumo      = serializers.PrimaryKeyRelatedField(source="id_insumo", read_only=True)
    insumoNombre  = serializers.CharField(source="id_insumo.nombre",      read_only=True)
    idLote        = serializers.PrimaryKeyRelatedField(source="id_lote",   read_only=True)
    numLote       = serializers.CharField(source="id_lote.num_lote",       read_only=True, default="")
    costoUnitario = serializers.DecimalField(source="costo_unitario", max_digits=14, decimal_places=4, allow_null=True)

    class Meta:
        model  = EntradaInventarioDetail
        fields = ["id", "idInsumo", "insumoNombre", "idLote", "numLote", "cantidad", "costoUnitario"]


class EntradaInventarioSerializer(serializers.ModelSerializer):
    id           = serializers.IntegerField(source="pk", read_only=True)
    idAlmacen    = serializers.PrimaryKeyRelatedField(source="id_almacen",   read_only=True)
    almacenNombre = serializers.CharField(source="id_almacen.nombre",        read_only=True)
    idProveedor  = serializers.PrimaryKeyRelatedField(source="id_proveedor", read_only=True)
    numRemision  = serializers.CharField(source="num_remision")
    fchEntrada   = serializers.DateField(source="fch_entrada")
    detalles     = EntradaDetalleSerializer(many=True, read_only=True)
    isActive     = serializers.BooleanField(source="is_active", read_only=True)
    createdAt    = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model  = EntradaInventario
        fields = [
            "id", "idAlmacen", "almacenNombre", "idProveedor", "numRemision",
            "fchEntrada", "observaciones", "isActive", "createdAt", "detalles",
        ]


class KardexMovimientoSerializer(serializers.ModelSerializer):
    id              = serializers.IntegerField(source="pk", read_only=True)
    idInsumo        = serializers.PrimaryKeyRelatedField(source="id_insumo",  read_only=True)
    insumoNombre    = serializers.CharField(source="id_insumo.nombre",         read_only=True)
    idLote          = serializers.PrimaryKeyRelatedField(source="id_lote",     read_only=True)
    numLote         = serializers.CharField(source="id_lote.num_lote",         read_only=True, default="")
    idAlmacen       = serializers.PrimaryKeyRelatedField(source="id_almacen",  read_only=True)
    tipoMovimiento  = serializers.CharField(source="tipo_movimiento")
    saldoResultante = serializers.DecimalField(source="saldo_resultante",      max_digits=14, decimal_places=4)
    refModelo       = serializers.CharField(source="ref_modelo")
    refId           = serializers.IntegerField(source="ref_id")
    fchMovimiento   = serializers.DateTimeField(source="fch_movimiento",       read_only=True)

    class Meta:
        model  = KardexMovimiento
        fields = [
            "id", "idInsumo", "insumoNombre", "idLote", "numLote", "idAlmacen",
            "tipoMovimiento", "cantidad", "saldoResultante", "refModelo", "refId", "fchMovimiento",
        ]


class ExistenciaAlmacenSerializer(serializers.ModelSerializer):
    id           = serializers.IntegerField(source="pk", read_only=True)
    idInsumo     = serializers.PrimaryKeyRelatedField(source="id_insumo",  read_only=True)
    insumoNombre = serializers.CharField(source="id_insumo.nombre",         read_only=True)
    insumoCode   = serializers.CharField(source="id_insumo.codigo",         read_only=True)
    idLote       = serializers.PrimaryKeyRelatedField(source="id_lote",     read_only=True)
    numLote      = serializers.CharField(source="id_lote.num_lote",         read_only=True, default="")
    caducidad    = serializers.DateField(source="id_lote.fecha_caducidad",  read_only=True, default=None)
    idAlmacen    = serializers.PrimaryKeyRelatedField(source="id_almacen",  read_only=True)
    almacenNombre = serializers.CharField(source="id_almacen.nombre",       read_only=True)
    stockMinimo  = serializers.DecimalField(source="id_insumo.stock_minimo", max_digits=14, decimal_places=4, read_only=True)
    bajoCritico  = serializers.SerializerMethodField()

    class Meta:
        model  = ExistenciaAlmacen
        fields = [
            "id", "idInsumo", "insumoNombre", "insumoCode", "idLote", "numLote",
            "caducidad", "idAlmacen", "almacenNombre", "cantidad", "stockMinimo", "bajoCritico",
        ]

    def get_bajoCritico(self, obj: ExistenciaAlmacen) -> bool:
        return obj.cantidad <= obj.id_insumo.stock_minimo


# ─── Phase 3: Salidas ────────────────────────────────────────────────────────

class SalidaDetalleSerializer(serializers.ModelSerializer):
    id           = serializers.IntegerField(source="pk", read_only=True)
    idInsumo     = serializers.PrimaryKeyRelatedField(source="id_insumo", read_only=True)
    insumoNombre = serializers.CharField(source="id_insumo.nombre",      read_only=True)
    idLote       = serializers.PrimaryKeyRelatedField(source="id_lote",  read_only=True)
    numLote      = serializers.CharField(source="id_lote.num_lote",      read_only=True, default="")

    class Meta:
        model  = SalidaInventarioDetail
        fields = ["id", "idInsumo", "insumoNombre", "idLote", "numLote", "cantidad"]


class SalidaInventarioSerializer(serializers.ModelSerializer):
    id            = serializers.IntegerField(source="pk", read_only=True)
    idAlmacen     = serializers.PrimaryKeyRelatedField(source="id_almacen", read_only=True)
    almacenNombre = serializers.CharField(source="id_almacen.nombre",       read_only=True)
    tipoSalida    = serializers.CharField(source="tipo_salida")
    numFolio      = serializers.CharField(source="num_folio")
    fchSalida     = serializers.DateField(source="fch_salida")
    detalles      = SalidaDetalleSerializer(many=True, read_only=True)
    isActive      = serializers.BooleanField(source="is_active",  read_only=True)
    createdAt     = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model  = SalidaInventario
        fields = [
            "id", "idAlmacen", "almacenNombre", "tipoSalida", "numFolio",
            "fchSalida", "motivo", "isActive", "createdAt", "detalles",
        ]


# ─── Phase 4: Conteo Físico ──────────────────────────────────────────────────

class ConteoDetalleSerializer(serializers.ModelSerializer):
    id           = serializers.IntegerField(source="pk", read_only=True)
    idInsumo     = serializers.PrimaryKeyRelatedField(source="id_insumo", read_only=True)
    insumoNombre = serializers.CharField(source="id_insumo.nombre",      read_only=True)
    idLote       = serializers.PrimaryKeyRelatedField(source="id_lote",  read_only=True)
    numLote      = serializers.CharField(source="id_lote.num_lote",      read_only=True, default="")
    cantSistema  = serializers.DecimalField(source="cant_sistema", max_digits=14, decimal_places=4)
    cantFisica   = serializers.DecimalField(source="cant_fisica",  max_digits=14, decimal_places=4)
    diferencia   = serializers.SerializerMethodField()

    class Meta:
        model  = ConteoFisicoDetalle
        fields = ["id", "idInsumo", "insumoNombre", "idLote", "numLote", "cantSistema", "cantFisica", "diferencia"]

    def get_diferencia(self, obj: ConteoFisicoDetalle):
        return obj.cant_fisica - obj.cant_sistema


class ConteoFisicoSerializer(serializers.ModelSerializer):
    id            = serializers.IntegerField(source="pk", read_only=True)
    idAlmacen     = serializers.PrimaryKeyRelatedField(source="id_almacen", read_only=True)
    almacenNombre = serializers.CharField(source="id_almacen.nombre",       read_only=True)
    fchConteo     = serializers.DateField(source="fch_conteo")
    fchCierre     = serializers.DateTimeField(source="fch_cierre",           read_only=True)
    detalles      = ConteoDetalleSerializer(many=True, read_only=True)
    isActive      = serializers.BooleanField(source="is_active",  read_only=True)
    createdAt     = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model  = ConteoFisico
        fields = [
            "id", "idAlmacen", "almacenNombre", "fchConteo", "observaciones",
            "cerrado", "fchCierre", "isActive", "createdAt", "detalles",
        ]


# ─── Phase 6: Consumos por Consulta ─────────────────────────────────────────

class MedicoNombreField(serializers.RelatedField):
    """Lee/escribe el médico por nombre completo (no por id) -- mismo patrón
    que Sucursal/EspecialidadNombreField en contratos_oxigeno. A diferencia
    de esos catálogos, el nombre de un médico no está garantizado único en
    la base: si hay colisión, se rechaza con un error explícito en vez de
    elegir uno al azar."""

    default_error_messages = {
        "does_not_exist": "No existe un médico con nombre '{value}'.",
        "multiple": "Hay más de un médico con el nombre '{value}' -- no se puede resolver de forma única.",
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", with_identity(CatMedico.objects.all()))
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_representation(self, obj):
        # display_name cubre médicos sin usuario (nombre propio en CatMedico).
        return display_name(obj)

    def to_internal_value(self, data):
        if not data:
            return None
        matches = list(annotate_display_name(self.get_queryset()).filter(medico_nombre=data)[:2])
        if not matches:
            self.fail("does_not_exist", value=data)
        if len(matches) > 1:
            self.fail("multiple", value=data)
        return matches[0]


class ConsumoDetalleSerializer(serializers.ModelSerializer):
    id           = serializers.IntegerField(source="pk", read_only=True)
    idInsumo     = serializers.PrimaryKeyRelatedField(source="id_insumo", read_only=True)
    insumoNombre = serializers.CharField(source="id_insumo.nombre",      read_only=True)
    idLote       = serializers.PrimaryKeyRelatedField(source="id_lote",  read_only=True)
    numLote      = serializers.CharField(source="id_lote.num_lote",      read_only=True, default="")

    class Meta:
        model  = ConsumoConsultaDetalle
        fields = ["id", "idInsumo", "insumoNombre", "idLote", "numLote", "cantidad"]


class ConsumoConsultaSerializer(serializers.ModelSerializer):
    id            = serializers.IntegerField(source="pk", read_only=True)
    idAlmacen     = serializers.PrimaryKeyRelatedField(source="id_almacen", read_only=True)
    almacenNombre = serializers.CharField(source="id_almacen.nombre",       read_only=True)
    idCita        = serializers.IntegerField(source="id_cita",               allow_null=True)
    medico        = MedicoNombreField()
    fchConsumo    = serializers.DateField(source="fch_consumo")
    detalles      = ConsumoDetalleSerializer(many=True, read_only=True)
    isActive      = serializers.BooleanField(source="is_active",  read_only=True)
    createdAt     = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model  = ConsumoConsulta
        fields = [
            "id", "idAlmacen", "almacenNombre", "idCita", "paciente", "medico",
            "fchConsumo", "observaciones", "isActive", "createdAt", "detalles",
        ]
