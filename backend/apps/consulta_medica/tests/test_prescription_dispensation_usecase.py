"""
Tests de sdd/dispensacion-farmacia (fase 7 de tasks.md).

IMPORTANTE (ver design, seccion "Testing Strategy" y gotcha de
config/settings.py:143): este suite corre sobre SQLite in-memory
(`"test" in sys.argv`). En SQLite el JSONField es texto plano y siempre
parsea, y `select_for_update()` es un no-op -- NINGUNO de estos tests
prueba el riesgo real de jsonb en Postgres ni la serializacion real de
locks concurrentes bajo carga. Esa verificacion es MANUAL contra Postgres
(fase 8 de tasks.md) y no puede sustituirse por este archivo.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.almacen_insumos.models.catalogos import (
    Almacen,
    CatCategoriaInsumo,
    CatInsumo,
    CatUnidadMedida,
)
from apps.almacen_insumos.models.farmacia import MedicamentoInsumo
from apps.almacen_insumos.models.kardex import ConsumoConsulta, ExistenciaAlmacen
from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCentroAtencion, CatCies, Consultorios, Medicamentos, Turnos
from apps.consulta_medica.models import PrescriptionAuthorization, VisitPrescriptionItem
from apps.consulta_medica.uses_case import prescription_dispensation_usecase as pdu
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

DISPENSE_PERMISSION = ["farmacia:recetas:dispensar"]


def _noop_audit_hook(**kwargs):
    return None


class ComputeQuantityUnitTests(SimpleTestCase):
    """7.1 -- Decimal puro, sin DB (factor_conversion entero/fraccionario)."""

    def test_factor_uno_es_identidad(self):
        self.assertEqual(pdu._compute_quantity(5, Decimal("1")), Decimal("5.0000"))

    def test_factor_entero_multiplica_sin_fraccion(self):
        result = pdu._compute_quantity(3, Decimal("2"))
        self.assertEqual(result, Decimal("6.0000"))
        self.assertEqual(result % 1, Decimal("0"))

    def test_factor_fraccionario_permitido_da_resultado_fraccionario(self):
        result = pdu._compute_quantity(3, Decimal("1.5"))
        self.assertEqual(result, Decimal("4.5000"))
        self.assertNotEqual(result % 1, Decimal("0"))

    def test_factor_fraccionario_se_detecta_por_modulo_para_rechazo(self):
        # Simula el gate real: `not permite_fraccion and computed % 1 != 0`.
        result = pdu._compute_quantity(1, Decimal("0.3333"))
        self.assertNotEqual(result % 1, Decimal("0"))

    def test_redondeo_half_up(self):
        result = pdu._compute_quantity(1, Decimal("0.00005"))
        self.assertEqual(result, Decimal("0.0001"))


class PrescriptionDispensationUseCaseTests(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_disp_test", correo="doctor_disp@example.com", clave_hash="x",
        ).id_usuario

        CatCies.objects.create(
            code="I10", description="HIPERTENSION ESENCIAL", version="CIE-10", is_active=True,
        )

        self.categoria = CatCategoriaInsumo.objects.create(nombre="Medicamentos Test")
        self.unidad = CatUnidadMedida.objects.create(nombre="Unidad Test", abreviacion="u")

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Dispensacion Test", code="DISP-TEST-001",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.almacen = Almacen.objects.create(
            nombre="Farmacia Test", tipo=Almacen.Tipo.FARMACIA, id_centro_atencion=self.centro,
        )

        self.med_a = Medicamentos.objects.create(
            name="Medicamento A", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
            is_controlled=False,
        )
        self.med_b = Medicamentos.objects.create(
            name="Medicamento B", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
            is_controlled=False,
        )
        self.med_sin_mapeo = Medicamentos.objects.create(
            name="Medicamento Sin Mapeo", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
            is_controlled=False,
        )

        self.insumo_a = CatInsumo.objects.create(
            nombre="Insumo A", codigo="INS-DISP-A",
            id_categoria=self.categoria, id_unidad=self.unidad,
        )
        self.insumo_b = CatInsumo.objects.create(
            nombre="Insumo B", codigo="INS-DISP-B",
            id_categoria=self.categoria, id_unidad=self.unidad,
        )

        self.mapping_a = MedicamentoInsumo.objects.create(
            medicamento=self.med_a, insumo=self.insumo_a, factor_conversion=1,
        )
        self.mapping_b = MedicamentoInsumo.objects.create(
            medicamento=self.med_b, insumo=self.insumo_b, factor_conversion=1,
        )

    def _visit_in_consultation(self, consultorio=None):
        n = Visit.objects.count() + 1
        visit = Visit.objects.create(
            folio=f"DISP-{n}",
            no_exp=f"EXPDISP{9000 + n}",
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-DISP-{n}",
            status="en_consulta",
            consultorio=consultorio,
            nombre_paciente=f"Paciente {n}",
        )
        save_diagnosis(
            visit_id=visit.id_visit, roles=["DOCTOR"],
            primary_diagnosis="Dx de prueba", final_note="Nota de prueba",
            doctor_id=self.doctor_id,
            audit_hook=_noop_audit_hook,
        )
        return visit

    def _add_item(self, visit, medication, quantity):
        payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=medication.id, quantity=quantity, indications="Cada 8 horas",
            actor_id=self.doctor_id,
        )
        return payload["id"]

    def _prescription_id_for_visit(self, visit):
        from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
        return PrescriptionRepository.get_by_visit(visit).id_prescription

    # ------------------------------------------------------------------
    # 7.2 -- stock insuficiente multi-item -> 409, rollback total
    # ------------------------------------------------------------------
    def test_stock_insuficiente_multi_item_hace_rollback_total(self):
        visit = self._visit_in_consultation()
        item_a = self._add_item(visit, self.med_a, quantity=5)
        item_b = self._add_item(visit, self.med_b, quantity=3)
        prescription_id = self._prescription_id_for_visit(visit)

        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo_a, cantidad=10)
        # Insumo B se queda SIN stock a proposito.
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo_b, cantidad=0)

        with self.assertRaises(VisitDomainError) as raised:
            pdu.dispense(
                prescription_id, ["FARMACIA"],
                id_almacen=self.almacen.pk,
                item_requests=[
                    {"itemId": item_a, "quantity": 5},
                    {"itemId": item_b, "quantity": 3},
                ],
                actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
                audit_hook=_noop_audit_hook,
            )
        self.assertEqual(raised.exception.code, "INSUFFICIENT_STOCK")
        self.assertEqual(raised.exception.status_code, 409)

        # Rollback total: NADA se toco, ni siquiera el insumo A que si
        # tenia stock suficiente.
        existencia_a = ExistenciaAlmacen.objects.get(id_almacen=self.almacen, id_insumo=self.insumo_a)
        self.assertEqual(existencia_a.cantidad, Decimal("10.0000"))

        item_a_row = VisitPrescriptionItem.objects.get(pk=item_a)
        item_b_row = VisitPrescriptionItem.objects.get(pk=item_b)
        self.assertEqual(item_a_row.dispensation_status, VisitPrescriptionItem.DispensationStatus.PENDIENTE)
        self.assertEqual(item_b_row.dispensation_status, VisitPrescriptionItem.DispensationStatus.PENDIENTE)
        self.assertEqual(ConsumoConsulta.objects.count(), 0)

    # ------------------------------------------------------------------
    # 7.3 -- doble POST -> segundo 409, stock descontado una sola vez
    # ------------------------------------------------------------------
    def test_doble_dispensacion_del_mismo_item_es_rechazada(self):
        visit = self._visit_in_consultation()
        item_a = self._add_item(visit, self.med_a, quantity=5)
        prescription_id = self._prescription_id_for_visit(visit)
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo_a, cantidad=10)

        payload = pdu.dispense(
            prescription_id, ["FARMACIA"],
            id_almacen=self.almacen.pk,
            item_requests=[{"itemId": item_a, "quantity": 5}],
            actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
            audit_hook=_noop_audit_hook,
        )
        self.assertEqual(payload["items"][0]["dispensationStatus"], "dispensado")

        with self.assertRaises(VisitDomainError) as raised:
            pdu.dispense(
                prescription_id, ["FARMACIA"],
                id_almacen=self.almacen.pk,
                item_requests=[{"itemId": item_a, "quantity": 1}],
                actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
                audit_hook=_noop_audit_hook,
            )
        self.assertEqual(raised.exception.code, "ALREADY_DISPENSED")
        self.assertEqual(raised.exception.status_code, 409)

        # El stock solo se descarga UNA vez.
        existencia_a = ExistenciaAlmacen.objects.get(id_almacen=self.almacen, id_insumo=self.insumo_a)
        self.assertEqual(existencia_a.cantidad, Decimal("5.0000"))

    def test_dispensacion_que_excede_lo_prescrito_es_rechazada(self):
        visit = self._visit_in_consultation()
        item_a = self._add_item(visit, self.med_a, quantity=5)
        prescription_id = self._prescription_id_for_visit(visit)
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo_a, cantidad=10)

        with self.assertRaises(VisitDomainError) as raised:
            pdu.dispense(
                prescription_id, ["FARMACIA"],
                id_almacen=self.almacen.pk,
                item_requests=[{"itemId": item_a, "quantity": 6}],
                actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
                audit_hook=_noop_audit_hook,
            )
        self.assertEqual(raised.exception.code, "DISPENSATION_EXCEEDS_PRESCRIBED")
        self.assertEqual(raised.exception.status_code, 409)

    # ------------------------------------------------------------------
    # 7.4 -- medicamento sin mapeo -> 422, cero escrituras
    # ------------------------------------------------------------------
    def test_medicamento_sin_mapeo_rechaza_sin_escribir_nada(self):
        visit = self._visit_in_consultation()
        item_sin_mapeo = self._add_item(visit, self.med_sin_mapeo, quantity=2)
        prescription_id = self._prescription_id_for_visit(visit)

        with self.assertRaises(VisitDomainError) as raised:
            pdu.dispense(
                prescription_id, ["FARMACIA"],
                id_almacen=self.almacen.pk,
                item_requests=[{"itemId": item_sin_mapeo, "quantity": 2}],
                actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
                audit_hook=_noop_audit_hook,
            )
        self.assertEqual(raised.exception.code, "MEDICATION_NOT_MAPPED")
        self.assertEqual(raised.exception.status_code, 422)

        item_row = VisitPrescriptionItem.objects.get(pk=item_sin_mapeo)
        self.assertEqual(item_row.dispensation_status, VisitPrescriptionItem.DispensationStatus.PENDIENTE)
        self.assertEqual(item_row.dispensed_quantity, 0)
        self.assertEqual(ConsumoConsulta.objects.count(), 0)

    # ------------------------------------------------------------------
    # 7.5 -- receta mixta (mapeados + sin mapear) -> 201 parcial
    # ------------------------------------------------------------------
    def test_receta_mixta_dispensa_mapeados_y_deja_pendiente_el_resto(self):
        visit = self._visit_in_consultation()
        item_a = self._add_item(visit, self.med_a, quantity=2)
        item_sin_mapeo = self._add_item(visit, self.med_sin_mapeo, quantity=1)
        prescription_id = self._prescription_id_for_visit(visit)
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo_a, cantidad=10)

        # El caller (frontend) solo manda el item mapeado -- ver design,
        # Open Question #2 resuelta como 422 global si se INCLUYE un item
        # sin mapear, no un 207 parcial automatico.
        payload = pdu.dispense(
            prescription_id, ["FARMACIA"],
            id_almacen=self.almacen.pk,
            item_requests=[{"itemId": item_a, "quantity": 2}],
            actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
            audit_hook=_noop_audit_hook,
        )
        self.assertEqual(payload["items"][0]["dispensationStatus"], "dispensado")

        item_a_row = VisitPrescriptionItem.objects.get(pk=item_a)
        item_sin_mapeo_row = VisitPrescriptionItem.objects.get(pk=item_sin_mapeo)
        self.assertEqual(item_a_row.dispensation_status, VisitPrescriptionItem.DispensationStatus.DISPENSADO)
        self.assertEqual(item_sin_mapeo_row.dispensation_status, VisitPrescriptionItem.DispensationStatus.PENDIENTE)

    def test_dispensacion_parcial_deja_estatus_parcial(self):
        visit = self._visit_in_consultation()
        item_a = self._add_item(visit, self.med_a, quantity=5)
        prescription_id = self._prescription_id_for_visit(visit)
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=self.insumo_a, cantidad=10)

        payload = pdu.dispense(
            prescription_id, ["FARMACIA"],
            id_almacen=self.almacen.pk,
            item_requests=[{"itemId": item_a, "quantity": 2}],
            actor_id=self.doctor_id, permissions=DISPENSE_PERMISSION,
            audit_hook=_noop_audit_hook,
        )
        self.assertEqual(payload["items"][0]["dispensationStatus"], "parcial")

        item_row = VisitPrescriptionItem.objects.get(pk=item_a)
        self.assertEqual(item_row.dispensed_quantity, 2)
        self.assertEqual(item_row.dispensation_status, VisitPrescriptionItem.DispensationStatus.PARCIAL)

    def test_dispensar_sin_permiso_es_rechazado(self):
        visit = self._visit_in_consultation()
        item_a = self._add_item(visit, self.med_a, quantity=2)
        prescription_id = self._prescription_id_for_visit(visit)

        with self.assertRaises(VisitDomainError) as raised:
            pdu.dispense(
                prescription_id, ["FARMACIA"],
                id_almacen=self.almacen.pk,
                item_requests=[{"itemId": item_a, "quantity": 2}],
                actor_id=self.doctor_id, permissions=[],
                audit_hook=_noop_audit_hook,
            )
        self.assertEqual(raised.exception.code, "ROLE_NOT_ALLOWED")
        self.assertEqual(raised.exception.status_code, 403)

    # ------------------------------------------------------------------
    # Gate de autorizacion (verify report #543, desvio c): receta sin
    # PrescriptionAuthorization nunca creada, o con al menos una creada
    # -- en cuyo caso manda el status de la MAS RECIENTE (`-created_at`),
    # no la mas vieja. Aislado a `_ensure_prescription_authorized` en vez
    # de pasar por `dispense()` completo -- el gate es de solo lectura y
    # no depende de mapeo/stock/almacen.
    # ------------------------------------------------------------------
    def test_gate_autorizacion_sin_solicitud_no_bloquea(self):
        """Receta que nunca genero una PrescriptionAuthorization (solo
        medicamentos BASICO no controlados) -- get_latest_authorization_status
        devuelve None y el gate no debe lanzar PRESCRIPTION_NOT_AUTHORIZED."""
        visit = self._visit_in_consultation()
        self._add_item(visit, self.med_a, quantity=2)
        prescription_id = self._prescription_id_for_visit(visit)

        try:
            pdu._ensure_prescription_authorized(prescription_id)
        except VisitDomainError as exc:
            self.fail(
                f"El gate no debe bloquear una receta sin autorizacion previa, "
                f"pero lanzo {exc.code!r}."
            )

    def test_gate_autorizacion_pendiente_bloquea_con_409(self):
        visit = self._visit_in_consultation()
        self._add_item(visit, self.med_a, quantity=2)
        prescription_id = self._prescription_id_for_visit(visit)

        PrescriptionAuthorization.objects.create(
            prescription_id=prescription_id,
            visit=visit,
            status=PrescriptionAuthorization.Status.PENDIENTE,
        )

        with self.assertRaises(VisitDomainError) as raised:
            pdu._ensure_prescription_authorized(prescription_id)
        self.assertEqual(raised.exception.code, "PRESCRIPTION_NOT_AUTHORIZED")
        self.assertEqual(raised.exception.status_code, 409)

    def test_gate_autorizacion_rechazada_bloquea_con_409(self):
        visit = self._visit_in_consultation()
        self._add_item(visit, self.med_a, quantity=2)
        prescription_id = self._prescription_id_for_visit(visit)

        PrescriptionAuthorization.objects.create(
            prescription_id=prescription_id,
            visit=visit,
            status=PrescriptionAuthorization.Status.RECHAZADA,
        )

        with self.assertRaises(VisitDomainError) as raised:
            pdu._ensure_prescription_authorized(prescription_id)
        self.assertEqual(raised.exception.code, "PRESCRIPTION_NOT_AUTHORIZED")
        self.assertEqual(raised.exception.status_code, 409)

    def test_gate_autorizacion_usa_la_mas_reciente_no_la_mas_vieja(self):
        """Historico 1:N (ver docstring del modelo): una RECHAZADA vieja no
        debe bloquear si la solicitud MAS RECIENTE quedo AUTORIZADA."""
        visit = self._visit_in_consultation()
        self._add_item(visit, self.med_a, quantity=2)
        prescription_id = self._prescription_id_for_visit(visit)

        auth_vieja = PrescriptionAuthorization.objects.create(
            prescription_id=prescription_id,
            visit=visit,
            status=PrescriptionAuthorization.Status.RECHAZADA,
        )
        # `created_at` es auto_now_add -- se fuerza hacia el pasado via
        # queryset.update() (bypassa auto_now_add, a diferencia de .save()),
        # asi la segunda autorizacion queda como la mas reciente por reloj.
        PrescriptionAuthorization.objects.filter(pk=auth_vieja.pk).update(
            created_at=timezone.now() - timedelta(days=1),
        )

        PrescriptionAuthorization.objects.create(
            prescription_id=prescription_id,
            visit=visit,
            status=PrescriptionAuthorization.Status.AUTORIZADA,
        )

        try:
            pdu._ensure_prescription_authorized(prescription_id)
        except VisitDomainError as exc:
            self.fail(
                f"El gate debe usar la autorizacion mas reciente (AUTORIZADA), "
                f"no la vieja RECHAZADA, pero lanzo {exc.code!r}."
            )

    # ------------------------------------------------------------------
    # Preview (GET dispensation)
    # ------------------------------------------------------------------
    def test_preview_marca_computed_quantity_y_falta_de_mapeo(self):
        visit = self._visit_in_consultation()
        self._add_item(visit, self.med_a, quantity=3)
        self._add_item(visit, self.med_sin_mapeo, quantity=1)
        prescription_id = self._prescription_id_for_visit(visit)

        preview = pdu.get_dispensation_preview(
            prescription_id, ["FARMACIA"], permissions=DISPENSE_PERMISSION,
        )

        by_medication = {item["medicationId"]: item for item in preview["items"]}
        item_a = by_medication[self.med_a.id]
        item_sin_mapeo = by_medication[self.med_sin_mapeo.id]

        self.assertTrue(item_a["hasMapping"])
        self.assertEqual(item_a["computedQuantity"], "3.0000")
        self.assertFalse(item_sin_mapeo["hasMapping"])
        self.assertIsNone(item_sin_mapeo["computedQuantity"])

    # ------------------------------------------------------------------
    # 7.7 -- cola de pendientes filtra por idAlmacen (centro)
    # ------------------------------------------------------------------
    def test_cola_pendientes_filtra_por_id_almacen(self):
        turno = Turnos.objects.create(name="Matutino")
        consultorio_propio = Consultorios.objects.create(
            name="C1", numero=1, id_turn=turno, id_center=self.centro,
        )

        otro_centro = CatCentroAtencion.objects.create(
            name="Otro Centro Test", code="DISP-TEST-002",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        otro_almacen = Almacen.objects.create(
            nombre="Farmacia Otro Centro", tipo=Almacen.Tipo.FARMACIA, id_centro_atencion=otro_centro,
        )
        consultorio_otro = Consultorios.objects.create(
            name="C2", numero=2, id_turn=turno, id_center=otro_centro,
        )

        visit_propia = self._visit_in_consultation(consultorio=consultorio_propio)
        self._add_item(visit_propia, self.med_a, quantity=2)

        visit_otra = self._visit_in_consultation(consultorio=consultorio_otro)
        self._add_item(visit_otra, self.med_b, quantity=1)

        result = pdu.list_pending_dispensation_queue(
            ["FARMACIA"], permissions=DISPENSE_PERMISSION, id_almacen=self.almacen.pk,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["visitId"], visit_propia.id_visit)

        result_otro = pdu.list_pending_dispensation_queue(
            ["FARMACIA"], permissions=DISPENSE_PERMISSION, id_almacen=otro_almacen.pk,
        )
        self.assertEqual(result_otro["total"], 1)
        self.assertEqual(result_otro["items"][0]["visitId"], visit_otra.id_visit)
