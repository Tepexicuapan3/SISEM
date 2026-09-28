from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Medicamentos
from apps.consulta_medica.uses_case.allergy_usecase import create_allergy
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.recepcion.models import Visit


def _noop_audit_hook(**kwargs):
    return None


class PrescriptionItemAllergyCheckTests(TestCase):
    """Cruce receta<->alergia (change `alergias-unificadas`): decision del
    usuario fue advertencia con override auditado, nunca bloqueo duro -- ver
    `prescription_item_usecase._find_matching_allergy`/`add_prescription_item`."""

    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_allergy_test", correo="doctor_allergy@example.com", clave_hash="x",
        ).id_usuario

        CatCies.objects.create(
            code="J00", description="RESFRIADO COMUN", version="CIE-10", is_active=True,
        )

        self.penicilina = Medicamentos.objects.create(
            name="Penicilina G Benzatinica", generic_name="Penicilina",
            cuadro_basico=Medicamentos.CuadroBasico.BASICO, is_controlled=False,
        )
        self.paracetamol = Medicamentos.objects.create(
            name="Paracetamol 500mg", generic_name="Paracetamol",
            cuadro_basico=Medicamentos.CuadroBasico.BASICO, is_controlled=False,
        )

    def _visit_in_consultation(self, no_exp):
        visit = Visit.objects.create(
            folio=f"RXALLERGY-{Visit.objects.count() + 1}",
            no_exp=no_exp,
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-RXALLERGY-{Visit.objects.count() + 1}",
            status="en_consulta",
        )
        save_diagnosis(
            visit_id=visit.id_visit, roles=["DOCTOR"],
            primary_diagnosis="Dx de prueba", final_note="Nota de prueba",
            doctor_id=self.doctor_id,
            audit_hook=_noop_audit_hook,
        )
        return visit

    def test_no_allergy_creates_item_normally(self):
        visit = self._visit_in_consultation("EXP9201")

        payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.paracetamol.id, quantity=10, indications="Cada 8 horas",
            actor_id=self.doctor_id,
        )

        self.assertNotIn("requiresAcknowledgment", payload)
        self.assertNotIn("allergyWarningAcknowledged", payload)

    def test_matching_allergy_blocks_first_attempt_without_creating_item(self):
        visit = self._visit_in_consultation("EXP9202")
        create_allergy(
            "EXP9202", 0, ["DOCTOR"],
            {"category": "medication", "substance": "Penicilina", "severity": "severe"},
            actor_id=self.doctor_id, source="general", audit_hook=_noop_audit_hook,
        )

        payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.penicilina.id, quantity=1, indications="Una vez",
            actor_id=self.doctor_id,
        )

        self.assertTrue(payload.get("requiresAcknowledgment"))
        self.assertEqual(payload["allergyWarning"]["substance"], "Penicilina")
        self.assertEqual(payload["allergyWarning"]["severity"], "severe")

        from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
        prescription = PrescriptionRepository.get_by_visit(visit.id_visit)
        self.assertIsNone(prescription)

    def test_acknowledging_the_warning_creates_the_item(self):
        visit = self._visit_in_consultation("EXP9203")
        create_allergy(
            "EXP9203", 0, ["DOCTOR"],
            {"category": "medication", "substance": "Penicilina", "severity": "moderate"},
            actor_id=self.doctor_id, source="general", audit_hook=_noop_audit_hook,
        )

        payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.penicilina.id, quantity=1, indications="Una vez",
            actor_id=self.doctor_id,
            acknowledge_allergy_warning=True,
        )

        self.assertNotIn("requiresAcknowledgment", payload)
        self.assertEqual(payload["allergyWarningAcknowledged"]["substance"], "Penicilina")
        self.assertEqual(payload["medicationId"], self.penicilina.id)
