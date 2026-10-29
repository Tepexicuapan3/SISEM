from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Medicamentos
from apps.consulta_medica.uses_case.allergy_usecase import create_allergy
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.recepcion.models import Visit
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


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
            patient=_paciente_de_llave(no_exp, 0),
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
            {"allergyTypeId": 1, "substance": "Penicilina", "severity": "G"},
            actor_id=self.doctor_id, source="general", audit_hook=_noop_audit_hook,
        )

        payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.penicilina.id, quantity=1, indications="Una vez",
            actor_id=self.doctor_id,
        )

        self.assertTrue(payload.get("requiresAcknowledgment"))
        self.assertEqual(payload["allergyWarning"]["substance"], "Penicilina")
        self.assertEqual(payload["allergyWarning"]["severity"], "G")

        from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
        prescription = PrescriptionRepository.get_by_visit(visit.id_visit)
        self.assertIsNone(prescription)

    def test_acknowledging_the_warning_creates_the_item(self):
        visit = self._visit_in_consultation("EXP9203")
        create_allergy(
            "EXP9203", 0, ["DOCTOR"],
            {"allergyTypeId": 1, "substance": "Penicilina", "severity": "M"},
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


class LegacyAllergyWarningTests(PrescriptionItemAllergyCheckTests):
    """Diseño del legado del 2026-10-27: una alergia del sistema anterior que
    nadie confirmo ni descarto tambien alerta, marcada como sin confirmar."""

    LEGADO = [{"ref": "legado_actual:his_clinica:11:ds_alergias:0", "seccion": "alergias",
               "texto": "PENICILINA", "fecha": "2024-02-01", "origen": "his_clinica · legado_actual"}]

    def _con_legado(self, items=None):
        from unittest import mock

        return mock.patch(
            "apps.consulta_medica.services.legado_confirmacion.alergias_sin_confirmar",
            return_value=self.LEGADO if items is None else items,
        )

    def test_legacy_allergy_warns_marked_as_unconfirmed(self):
        visit = self._visit_in_consultation("EXP9301")
        with self._con_legado():
            payload = add_prescription_item(
                visit.id_visit, ["DOCTOR"], medication_id=self.penicilina.id, quantity=1,
                indications="Una vez", actor_id=self.doctor_id,
            )
        warning = payload["allergyWarning"]
        self.assertTrue(payload["requiresAcknowledgment"])
        self.assertEqual((warning["substance"], warning["fromLegacy"], warning["allergyId"]),
                         ("PENICILINA", True, None))

    def test_acknowledged_legacy_warning_creates_the_item(self):
        visit = self._visit_in_consultation("EXP9302")
        with self._con_legado():
            payload = add_prescription_item(
                visit.id_visit, ["DOCTOR"], medication_id=self.penicilina.id, quantity=1,
                indications="Una vez", actor_id=self.doctor_id, acknowledge_allergy_warning=True,
            )
        self.assertEqual(payload["allergyWarningAcknowledged"],
                         {"allergyId": None, "substance": "PENICILINA", "fromLegacy": True})

    def test_unrelated_legacy_allergy_does_not_warn(self):
        visit = self._visit_in_consultation("EXP9303")
        with self._con_legado():
            payload = add_prescription_item(
                visit.id_visit, ["DOCTOR"], medication_id=self.paracetamol.id, quantity=10,
                indications="Cada 8 horas", actor_id=self.doctor_id,
            )
        self.assertNotIn("requiresAcknowledgment", payload)

    def test_sires_allergy_wins_over_legacy(self):
        visit = self._visit_in_consultation("EXP9304")
        create_allergy(
            "EXP9304", 0, ["DOCTOR"],
            {"allergyTypeId": 1, "substance": "Penicilina", "severity": "G"},
            actor_id=self.doctor_id, source="general", audit_hook=_noop_audit_hook,
        )
        with self._con_legado() as legado:
            payload = add_prescription_item(
                visit.id_visit, ["DOCTOR"], medication_id=self.penicilina.id, quantity=1,
                indications="Una vez", actor_id=self.doctor_id,
            )
        self.assertEqual(payload["allergyWarning"]["severity"], "G")
        self.assertNotIn("fromLegacy", payload["allergyWarning"])
        legado.assert_not_called()
