"""
sdd/dispensacion-farmacia, tarea 2.1: `dispensacion_service.registrar_dispensacion`
crea ConsumoConsulta + N ConsumoConsultaDetalle(prescription_item=...) y NO
captura InsufficientStockError -- eso lo hace el use-case de consulta_medica,
FUERA de su propio transaction.atomic() (ver design seccion a).
"""
from decimal import Decimal

from django.test import TestCase

from apps.almacen_insumos.models.catalogos import Almacen, CatCategoriaInsumo, CatInsumo, CatUnidadMedida
from apps.almacen_insumos.models.kardex import ConsumoConsulta, ConsumoConsultaDetalle, ExistenciaAlmacen
from apps.almacen_insumos.services import dispensacion_service
from apps.almacen_insumos.services.kardex_service import InsufficientStockError
from apps.catalogos.models import CatCentroAtencion


class DispensacionServiceTests(TestCase):
    def setUp(self):
        centro = CatCentroAtencion.objects.create(
            name="Centro Dispensacion Service Test", code="DISPSVC-001",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.almacen = Almacen.objects.create(
            nombre="Farmacia Service Test", tipo=Almacen.Tipo.FARMACIA, id_centro_atencion=centro,
        )
        categoria = CatCategoriaInsumo.objects.create(nombre="Categoria Service Test")
        unidad = CatUnidadMedida.objects.create(nombre="Unidad Service Test", abreviacion="u")
        self.insumo = CatInsumo.objects.create(
            nombre="Insumo Service Test", codigo="INS-SVC-001",
            id_categoria=categoria, id_unidad=unidad,
        )

    def test_registrar_dispensacion_crea_consumo_y_detalle_y_descuenta_stock(self):
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo, cantidad=10)

        # prescription_item es nullable a proposito (ver models/kardex.py):
        # este test unitario de almacen_insumos no depende de un item de
        # receta real de consulta_medica -- ese enlace se cubre end-to-end
        # en apps.consulta_medica.tests.test_prescription_dispensation_usecase.
        consumo = dispensacion_service.registrar_dispensacion(
            almacen=self.almacen,
            lineas=[
                dispensacion_service.DispensacionLinea(
                    insumo_id=self.insumo.pk, cantidad=Decimal("4.0000"), prescription_item_id=None,
                ),
            ],
            created_by_id=1,
        )

        self.assertEqual(ConsumoConsulta.objects.count(), 1)
        detalle = ConsumoConsultaDetalle.objects.get(id_consumo=consumo)
        self.assertIsNone(detalle.prescription_item_id)
        self.assertEqual(detalle.cantidad, Decimal("4.0000"))

        existencia = ExistenciaAlmacen.objects.get(id_almacen=self.almacen, id_insumo=self.insumo)
        self.assertEqual(existencia.cantidad, Decimal("6.0000"))

    def test_registrar_dispensacion_no_captura_insufficient_stock_error(self):
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo, cantidad=1)

        with self.assertRaises(InsufficientStockError):
            dispensacion_service.registrar_dispensacion(
                almacen=self.almacen,
                lineas=[
                    dispensacion_service.DispensacionLinea(
                        insumo_id=self.insumo.pk, cantidad=Decimal("5.0000"), prescription_item_id=None,
                    ),
                ],
                created_by_id=1,
            )
