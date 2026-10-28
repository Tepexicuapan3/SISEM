"""
Identidad del paciente en PACIENTE (`Patient`): CURP y sexo
(H/M/X), versionados como el resto de la historia; y limpieza del texto
libre de alergias (deprecado a favor de `Allergy`).
"""
from django.core.cache import cache
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.consulta_medica.models import Patient, PatientRevision
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase

VALID_CURP = "PEGJ850315HDFRRN09"


class ClinicalHistoryIdentityApiTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.no_exp = "EXPID1"
        self.url = f"/api/v1/patients/{self.no_exp}/profile?pkNum=0"
        self._login_doctor()

    def _patch(self, body):
        return self.client.patch(
            self.url, body, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def test_saves_and_returns_curp_and_sex(self):
        response = self._patch({"curp": VALID_CURP, "sex": "M"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["curp"], VALID_CURP)
        self.assertEqual(response.data["sex"], "M")
        read = self.client.get(self.url)
        self.assertEqual(read.data["curp"], VALID_CURP)
        self.assertEqual(read.data["sex"], "M")

    def test_normalizes_curp_to_uppercase_and_blank_to_null(self):
        # VALID_CURP es de hombre: el sexo tiene que coincidir con su letra 11 (5.1).
        normalized = self._patch({"curp": f"  {VALID_CURP.lower()} ", "sex": "M"})
        cleared = self._patch({"curp": "", "sex": ""})

        self.assertEqual(normalized.data["curp"], VALID_CURP)
        self.assertEqual(normalized.data["sex"], "M")
        self.assertIsNone(cleared.data["curp"])
        self.assertIsNone(cleared.data["sex"])

    def test_rejects_invalid_curp_and_sex(self):
        response = self._patch({"curp": "PEGJ851315HDFRRN09", "sex": "Z"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(set(response.data["details"]), {"curp", "sex"})
        self.assertFalse(Patient.objects.filter(no_exp=self.no_exp).exclude(curp=None).exists())

    def test_overwriting_curp_is_versioned_and_audited(self):
        self._patch({"curp": VALID_CURP, "sex": "M"})

        self._patch({"curp": "PEGJ850315MDFRRN01", "sex": "F"})

        revision = PatientRevision.objects.get()
        self.assertEqual(revision.previous_curp, VALID_CURP)
        self.assertEqual(revision.previous_sex, "M")
        event = AuditoriaEvento.objects.filter(accion="PatientProfileUpdated").latest("id_evento")
        self.assertEqual(event.datos_antes["curp"], VALID_CURP)
        self.assertEqual(sorted(event.datos_despues["changedFields"]), ["curp", "sex"])

    def test_accepts_legacy_phone_format_longer_than_15(self):
        legacy_phone = "cel 55-1234-5678 tel 5555-5555 ext 12345"

        response = self._patch({"phone": legacy_phone})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone"], legacy_phone)

    def test_allergies_free_text_is_no_longer_exposed_nor_writable(self):
        response = self._patch({"allergies": "Penicilina", "sex": "F"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("allergies", response.data)


