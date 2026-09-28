from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies
from apps.consulta_medica.uses_case.consultation_usecase import (
    add_secondary_diagnosis,
    get_secondary_diagnoses,
    save_diagnosis,
)
from apps.consulta_medica.uses_case.patient_history_usecase import (
    get_patient_consultations_history,
)
from apps.recepcion.models import Visit

VIH_PERMISSION = ["clinico:diagnosticos_vih:read"]


def _noop_audit_hook(**kwargs):
    return None


class DiagnosisRedactionTests(TestCase):
    """Diagnosticos sensibles (change `diagnosticos-sensibles`): decision
    del usuario fue redactar SOLO el diagnostico (codigo/descripcion/texto
    ligado), nunca el registro completo -- ver
    `consulta_medica.services.diagnosis_redaction_service`."""

    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_redaction_test", correo="doctor_redaction@example.com", clave_hash="x",
        ).id_usuario

        self.cie_vih = CatCies.objects.create(
            code="B20", description="ENFERMEDAD POR VIH", version="CIE-10", is_active=True,
        )
        self.cie_normal = CatCies.objects.create(
            code="J00", description="RESFRIADO COMUN", version="CIE-10", is_active=True,
        )

    def _visit_with_diagnosis(self, no_exp, *, cie_code):
        visit = Visit.objects.create(
            folio=f"REDACT-{Visit.objects.count() + 1}",
            no_exp=no_exp,
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-REDACT-{Visit.objects.count() + 1}",
            status="en_consulta",
        )
        save_diagnosis(
            visit_id=visit.id_visit, roles=["DOCTOR"],
            primary_diagnosis="VIH confirmado por laboratorio", final_note="Nota de prueba",
            doctor_id=self.doctor_id, cie_code=cie_code,
            audit_hook=_noop_audit_hook,
        )
        return visit

    # ── Historial de consultas (VisitConsultation.cie) ──────────────────

    def test_consultation_history_redacts_sensitive_diagnosis_without_permission(self):
        self._visit_with_diagnosis("EXP9301", cie_code=self.cie_vih.code)

        result = get_patient_consultations_history("EXP9301", 0, ["DOCTOR"], permissions=[])

        item = result["items"][0]
        self.assertIsNone(item["cieCode"])
        self.assertEqual(item["cieDescription"], "Diagnóstico restringido")
        self.assertEqual(item["primaryDiagnosis"], "Información restringida")
        self.assertTrue(item["restricted"])
        self.assertEqual(result["redactedVisitIds"], [item["visitId"]])
        # El resto del registro se sirve normal -- decision del usuario.
        self.assertEqual(item["finalNote"], "Nota de prueba")
        self.assertIsNotNone(item["doctorId"])

    def test_consultation_history_shows_diagnosis_with_permission(self):
        self._visit_with_diagnosis("EXP9302", cie_code=self.cie_vih.code)

        result = get_patient_consultations_history(
            "EXP9302", 0, ["DOCTOR"], permissions=VIH_PERMISSION,
        )

        item = result["items"][0]
        self.assertEqual(item["cieCode"], self.cie_vih.code)
        self.assertEqual(item["cieDescription"], "ENFERMEDAD POR VIH")
        self.assertEqual(item["primaryDiagnosis"], "VIH confirmado por laboratorio")
        self.assertFalse(item["restricted"])
        self.assertEqual(result["redactedVisitIds"], [])

    def test_consultation_history_does_not_redact_non_sensitive_diagnosis(self):
        self._visit_with_diagnosis("EXP9303", cie_code=self.cie_normal.code)

        result = get_patient_consultations_history("EXP9303", 0, ["DOCTOR"], permissions=[])

        item = result["items"][0]
        self.assertEqual(item["cieCode"], self.cie_normal.code)
        self.assertFalse(item["restricted"])

    # ── Diagnosticos secundarios (VisitDiagnosis.cie) ───────────────────

    def test_secondary_diagnosis_redacted_without_permission(self):
        visit = self._visit_with_diagnosis("EXP9304", cie_code=self.cie_normal.code)
        add_secondary_diagnosis(
            visit.id_visit, ["DOCTOR"], cie_code=self.cie_vih.code, notes="VIH, ver expediente",
            doctor_id=self.doctor_id,
        )

        result = get_secondary_diagnoses(visit.id_visit, ["DOCTOR"], permissions=[])

        item = result["items"][0]
        self.assertIsNone(item["cieCode"])
        self.assertEqual(item["cieDescription"], "Diagnóstico restringido")
        self.assertEqual(item["notes"], "Información restringida")
        self.assertTrue(item["restricted"])
        self.assertEqual(result["redactedDiagnosisIds"], [item["id"]])

    def test_secondary_diagnosis_visible_with_permission(self):
        visit = self._visit_with_diagnosis("EXP9305", cie_code=self.cie_normal.code)
        add_secondary_diagnosis(
            visit.id_visit, ["DOCTOR"], cie_code=self.cie_vih.code, notes="VIH, ver expediente",
            doctor_id=self.doctor_id,
        )

        result = get_secondary_diagnoses(visit.id_visit, ["DOCTOR"], permissions=VIH_PERMISSION)

        item = result["items"][0]
        self.assertEqual(item["cieCode"], self.cie_vih.code)
        self.assertEqual(item["notes"], "VIH, ver expediente")
        self.assertFalse(item["restricted"])
