from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views.catalogos import (
    AlmacenViewSet,
    CatCategoriaInsumoViewSet,
    CatInsumoViewSet,
    CatProveedorViewSet,
    CatUnidadMedidaViewSet,
)
from .views.farmacia import MedicamentoInsumoViewSet
from .views.kardex import (
    ConteoFisicoViewSet,
    ConsumoConsultaViewSet,
    DashboardAlmacenView,
    EntradaInventarioViewSet,
    ExistenciaViewSet,
    KardexMovimientoViewSet,
    LoteInsumoViewSet,
    SalidaInventarioViewSet,
)

router = DefaultRouter()
# Catálogos base
router.register(r"almacen/unidades-medida",  CatUnidadMedidaViewSet,    basename="almacen-unidad-medida")
router.register(r"almacen/categorias",       CatCategoriaInsumoViewSet, basename="almacen-categoria")
router.register(r"almacen/proveedores",      CatProveedorViewSet,       basename="almacen-proveedor")
router.register(r"almacen/insumos",          CatInsumoViewSet,          basename="almacen-insumo")
router.register(r"almacen/almacenes",        AlmacenViewSet,            basename="almacen-almacen")
router.register(r"almacen/medicamento-insumos", MedicamentoInsumoViewSet, basename="almacen-medicamento-insumo")
# Kardex engine
router.register(r"almacen/lotes",            LoteInsumoViewSet,         basename="almacen-lote")
router.register(r"almacen/entradas",         EntradaInventarioViewSet,  basename="almacen-entrada")
router.register(r"almacen/kardex",           KardexMovimientoViewSet,   basename="almacen-kardex")
router.register(r"almacen/existencias",      ExistenciaViewSet,         basename="almacen-existencia")
# Phase 3-6
router.register(r"almacen/salidas",          SalidaInventarioViewSet,   basename="almacen-salida")
router.register(r"almacen/conteos",          ConteoFisicoViewSet,       basename="almacen-conteo")
router.register(r"almacen/consumos",         ConsumoConsultaViewSet,    basename="almacen-consumo")

urlpatterns = [
    path("", include(router.urls)),
    path("almacen/dashboard/", DashboardAlmacenView.as_view(), name="almacen-dashboard"),
]
