"""Via, frecuencia y duracion de cada medicamento (RIS art. 30; D8 de
docs/plans/receta-diseno-stc.md). Obligatorias para cada renglon NUEVO; los
renglones ya guardados quedan con las columnas vacias."""

from django.test import SimpleTestCase, TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import Medicamentos
from apps.consulta_medica.impresion.receta import _administration_text
from apps.consulta_medica.models import VisitPrescriptionItem
from apps.consulta_medica.serializers import AddPrescriptionItemSerializer
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.tests.receta_fixtures import ADMINISTRATION


def _noop_audit_hook(**kwargs):
    return None


class AddPrescriptionItemAdministrationTests(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(usuario="dr_via", clave_hash="x").id_usuario
        self.paracetamol = Medicamentos.objects.create(name="Paracetamol 500mg", generic_name="Paracetamol")
        self.visit = Visit.objects.create(
            folio="RXVIA-1", patient=_paciente_de_llave("EXP9701", 0),
            arrival_type=Visit.ArrivalType.WALK_IN, status="en_consulta",
        )
        save_diagnosis(
            visit_id=self.visit.id_visit, roles=["DOCTOR"], primary_diagnosis="Dx",
            final_note="Nota", doctor_id=self.doctor_id, audit_hook=_noop_audit_hook,
        )

    def _add(self, **overrides):
        data = dict(
            medication_id=self.paracetamol.id, quantity=1, indications="Despues de comer",
            dose="1 tab", actor_id=self.doctor_id, **ADMINISTRATION,
        )
        data.update(overrides)
        return add_prescription_item(self.visit.id_visit, ["DOCTOR"], **data)

    def test_stores_route_frequency_and_duration(self):
        payload = self._add()
        item = VisitPrescriptionItem.objects.get(pk=payload["id"])
        self.assertEqual((item.route, item.frequency, item.duration), ("oral", "Cada 8 horas", "5 dias"))
        self.assertEqual(payload["route"], "oral")
        self.assertEqual(payload["routeLabel"], "Oral")
        self.assertEqual(payload["frequency"], "Cada 8 horas")
        self.assertEqual(payload["duration"], "5 dias")

    def test_each_field_is_required(self):
        for field in ("route", "frequency", "duration"):
            for empty in (None, "", "   "):
                with self.subTest(field=field, value=empty), self.assertRaises(VisitDomainError) as ctx:
                    self._add(**{field: empty})
                self.assertEqual(ctx.exception.status_code, 422)
                self.assertIn(field, ctx.exception.details)
        self.assertFalse(VisitPrescriptionItem.objects.exists())

    def test_unknown_route_is_rejected(self):
        with self.assertRaises(VisitDomainError) as ctx:
            self._add(route="telepatica")
        self.assertIn("route", ctx.exception.details)

    def test_texts_are_trimmed(self):
        payload = self._add(frequency="  Cada 12 horas ", duration=" 3 dias ")
        self.assertEqual((payload["frequency"], payload["duration"]), ("Cada 12 horas", "3 dias"))

    def test_existing_item_without_administration_still_serializes(self):
        payload = self._add()
        VisitPrescriptionItem.objects.filter(pk=payload["id"]).update(route=None, frequency=None, duration=None)
        item = VisitPrescriptionItem.objects.select_related("prescription", "medication").get(pk=payload["id"])
        from apps.consulta_medica.repositories.prescription_item_repository import PrescriptionItemRepository
        contract = PrescriptionItemRepository.to_contract(item)
        self.assertEqual((contract["route"], contract["routeLabel"], contract["frequency"]), (None, None, None))


class AddPrescriptionItemSerializerTests(SimpleTestCase):
    def test_accepts_administration_fields(self):
        serializer = AddPrescriptionItemSerializer(data={
            "medicationId": 1, "quantity": 1, "indications": "x",
            "route": "oral", "frequency": "Cada 8 horas", "duration": "5 dias",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["route"], "oral")

    def test_length_limits(self):
        serializer = AddPrescriptionItemSerializer(data={
            "medicationId": 1, "quantity": 1, "indications": "x",
            "route": "oral", "frequency": "x" * 61, "duration": "x" * 61,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("frequency", serializer.errors)
        self.assertIn("duration", serializer.errors)


class RecetaAdministrationTextTests(SimpleTestCase):
    def test_joins_dose_route_frequency_duration_and_indications(self):
        row = {"dose": "1 tab", "route_label": "Oral", "frequency": "Cada 8 horas",
               "duration": "5 dias", "indications": "Despues de comer"}
        self.assertEqual(
            _administration_text(row), "1 tab · Oral · Cada 8 horas · 5 dias · Despues de comer",
        )

    def test_old_item_without_administration_prints_as_before(self):
        row = {"dose": "1 tab", "route_label": "", "frequency": "", "duration": "", "indications": "Cada 8 h"}
        self.assertEqual(_administration_text(row), "1 tab · Cada 8 h")


class PrescriptionItemAuthorizationFlagsTests(AddPrescriptionItemAdministrationTests):
    """El renglon dice si su medicamento pide autorizacion (especial o
    controlado), para avisarle al medico antes de cerrar."""

    def test_basic_medication_does_not_require_authorization(self):
        payload = self._add()
        self.assertEqual(payload["cuadroBasico"], "BASICO")
        self.assertFalse(payload["isControlled"])
        self.assertFalse(payload["requiresAuthorization"])

    def test_controlled_or_special_requires_authorization(self):
        controlled = Medicamentos.objects.create(name="Clonazepam 2mg", is_controlled=True)
        special = Medicamentos.objects.create(
            name="Insulina glargina", cuadro_basico=Medicamentos.CuadroBasico.ESPECIAL,
        )
        self.assertTrue(self._add(medication_id=controlled.id)["requiresAuthorization"])
        self.assertTrue(self._add(medication_id=special.id)["requiresAuthorization"])
