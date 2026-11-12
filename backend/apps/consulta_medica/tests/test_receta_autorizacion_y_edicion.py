"""Autorizacion de receta al finalizar la consulta y edicion de renglones.

Decisiones del usuario (2026-11-12):
- El aviso al autorizador (solicitud en el motor) sale al FINALIZAR la
  consulta, con la receta completa; el registro de la autorizacion se sigue
  creando al agregar, como siempre.
- Un renglon se corrige mientras la consulta este abierta y no se haya
  surtido; el medicamento no cambia (se quita y se agrega otro).
- Si se edita un especial o controlado y la autorizacion ya estaba resuelta,
  la receta vuelve a pendiente.
"""
from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Medicamentos
from apps.consulta_medica.models import PrescriptionAuthorization, VisitPrescriptionItem
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.consulta_medica.tests.receta_fixtures import ADMINISTRATION
from apps.consulta_medica.uses_case.consultation_usecase import close_consultation, save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import (
    add_prescription_item,
    cancel_prescription_item,
    update_prescription_item,
)
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError


def _noop_audit_hook(**kwargs):
    return None


class _RecetaBase(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(usuario="dr_cierre", clave_hash="x").id_usuario
        CatCies.objects.create(code="I10", description="HIPERTENSION", version="CIE-10", is_active=True)
        self.basico = Medicamentos.objects.create(name="Paracetamol 500mg", max_quantity=3)
        self.especial = Medicamentos.objects.create(
            name="Insulina glargina", cuadro_basico=Medicamentos.CuadroBasico.ESPECIAL,
        )
        self.controlado = Medicamentos.objects.create(name="Clonazepam 2mg", is_controlled=True)
        self.visit = Visit.objects.create(
            folio=f"RXCIERRE-{Visit.objects.count() + 1}",
            patient=paciente_de_llave(f"EXP{8800 + Visit.objects.count()}", 0),
            arrival_type=Visit.ArrivalType.WALK_IN, status="en_consulta",
        )
        save_diagnosis(
            visit_id=self.visit.id_visit, roles=["DOCTOR"], primary_diagnosis="Dx",
            final_note="Nota", doctor_id=self.doctor_id, audit_hook=_noop_audit_hook,
        )

    def _add(self, medication, **overrides):
        data = dict(
            medication_id=medication.id, quantity=1, indications="Despues de comer",
            dose="1 tab", actor_id=self.doctor_id, **ADMINISTRATION,
        )
        data.update(overrides)
        return add_prescription_item(self.visit.id_visit, ["DOCTOR"], **data)

    def _close(self):
        return close_consultation(
            visit_id=self.visit.id_visit, roles=["DOCTOR"], primary_diagnosis="Dx",
            final_note="Nota", doctor_id=self.doctor_id, cie_code="I10", morbidity="1",
            audit_hook=_noop_audit_hook,
        )

    def _update(self, item_id, audit_hook=_noop_audit_hook, **changes):
        data = dict(
            quantity=1, indications="Despues de comer", dose="1 tab", actor_id=self.doctor_id,
            **ADMINISTRATION,
        )
        data.update(changes)
        return update_prescription_item(
            self.visit.id_visit, item_id, ["DOCTOR"], audit_hook=audit_hook, **data,
        )


class AutorizacionAlCerrarTests(_RecetaBase):
    def test_al_cerrar_la_pendiente_queda_con_los_conteos_de_la_receta_completa(self):
        self._add(self.especial)
        self._add(self.basico)
        self._add(self.controlado)

        self._close()

        authorization = PrescriptionAuthorization.objects.get()
        self.assertEqual(authorization.status, PrescriptionAuthorization.Status.PENDIENTE)
        self.assertEqual(
            (authorization.medications_count, authorization.specialized_count, authorization.controlled_count),
            (3, 1, 1),
        )
        self.assertEqual(authorization.prescribed_by_id, self.doctor_id)

    def test_al_cerrar_solo_con_basicos_no_pide_autorizacion(self):
        self._add(self.basico)
        self._close()
        self.assertEqual(PrescriptionAuthorization.objects.count(), 0)


class EditarRenglonTests(_RecetaBase):
    def test_corrige_los_datos_del_renglon_y_lo_audita(self):
        item = self._add(self.basico)
        calls = []

        payload = self._update(
            item["id"], audit_hook=lambda **kw: calls.append(kw),
            indications="Despues de cada comida", frequency="Cada 12 horas", duration="7 dias",
            route="sublingual", dose="2 tab", quantity=2,
        )

        self.assertEqual(payload["indications"], "Despues de cada comida")
        self.assertEqual(payload["frequency"], "Cada 12 horas")
        self.assertEqual(payload["routeLabel"], "Sublingual")
        self.assertEqual(payload["quantity"], 2)
        self.assertEqual(payload["medicationId"], self.basico.id)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["datos_antes"]["indications"], "Despues de comer")
        self.assertEqual(calls[0]["datos_despues"]["indications"], "Despues de cada comida")

    def test_valida_igual_que_al_agregar(self):
        item = self._add(self.basico)
        for changes, field in (
            ({"frequency": ""}, "frequency"),
            ({"indications": "  "}, "indications"),
            ({"quantity": 4}, "quantity"),
        ):
            with self.subTest(field=field), self.assertRaises(VisitDomainError) as ctx:
                self._update(item["id"], **changes)
            self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
            self.assertIn(field, ctx.exception.details)

    def test_no_se_edita_con_la_consulta_cerrada(self):
        item = self._add(self.basico)
        self._close()
        with self.assertRaises(VisitDomainError) as ctx:
            self._update(item["id"], indications="Otra")
        self.assertEqual(ctx.exception.code, "PRESCRIPTION_LOCKED")

    def test_no_se_edita_lo_surtido(self):
        item = self._add(self.basico)
        VisitPrescriptionItem.objects.filter(pk=item["id"]).update(dispensed_quantity=1)
        with self.assertRaises(VisitDomainError) as ctx:
            self._update(item["id"], indications="Otra")
        self.assertEqual(ctx.exception.code, "PRESCRIPTION_ITEM_DISPENSED")

    def test_no_se_edita_un_renglon_quitado(self):
        item = self._add(self.basico)
        cancel_prescription_item(
            self.visit.id_visit, item["id"], ["DOCTOR"], actor_id=self.doctor_id, audit_hook=_noop_audit_hook,
        )
        with self.assertRaises(VisitDomainError) as ctx:
            self._update(item["id"], indications="Otra")
        self.assertEqual(ctx.exception.code, "PRESCRIPTION_ITEM_NOT_FOUND")

    def test_editar_un_especial_con_autorizacion_resuelta_la_vuelve_a_pendiente(self):
        item = self._add(self.especial)
        previous = PrescriptionAuthorization.objects.get()
        PrescriptionAuthorization.objects.filter(pk=previous.pk).update(
            status=PrescriptionAuthorization.Status.AUTORIZADA,
        )

        self._update(item["id"], indications="Aplicar por la noche")

        latest = PrescriptionAuthorization.objects.order_by("-created_at", "-pk").first()
        self.assertNotEqual(latest.pk, previous.pk)
        self.assertEqual(latest.status, PrescriptionAuthorization.Status.PENDIENTE)

    def test_editar_un_basico_no_pide_autorizacion(self):
        item = self._add(self.basico)
        self._update(item["id"], indications="Otra")
        self.assertEqual(PrescriptionAuthorization.objects.count(), 0)
