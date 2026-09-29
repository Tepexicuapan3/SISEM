"""
BITACORA_ACCESO (documento "Historia Clinica Unificada"): quien vio,
exporto o modifico la historia de cada paciente, en su tabla propia. Las
lecturas se deduplican por (actor, no_exp, pk_num, recurso); nada de esto
bloquea nunca la operacion.
"""
from unittest.mock import patch

from django.core.cache import cache
from rest_framework import status

from apps.administracion.models import BitacoraAcceso
from apps.consulta_medica.services.record_access_audit_service import RecordSection
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase


class PatientRecordAccessAuditTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.no_exp = "EXPACC1"
        self._login_doctor()

    def _reads(self):
        return BitacoraAcceso.objects.filter(accion=BitacoraAcceso.Accion.VER)

    def _get(self, path):
        return self.client.get(path, HTTP_X_REQUEST_ID=self.request_id)

    def test_clinical_history_read_writes_access_entry(self):
        response = self._get(f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        entry = self._reads().get()
        self.assertEqual(entry.usuario_id, self.doctor_user.id_usuario)
        self.assertEqual(entry.cd_usuario, "audit_doctor_user")
        self.assertEqual((entry.no_exp, entry.tp_paciente), (self.no_exp, 2))
        self.assertEqual(entry.recurso, RecordSection.CLINICAL_HISTORY)
        self.assertEqual(entry.restringidos, 0)

    def test_repeated_read_of_same_section_is_deduplicated(self):
        path = f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=0"
        self._get(path)
        self._get(path)
        self._get(path)

        self.assertEqual(self._reads().count(), 1)

    def test_each_section_and_family_member_is_logged_separately(self):
        self._get(f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=0")
        self._get(f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=1")
        self._get(f"/api/v1/patients/{self.no_exp}/allergies?pkNum=0")

        self.assertEqual(
            sorted(self._reads().values_list("tp_paciente", "recurso")),
            [
                (0, RecordSection.ALLERGIES),
                (0, RecordSection.CLINICAL_HISTORY),
                (1, RecordSection.CLINICAL_HISTORY),
            ],
        )

    def test_read_still_succeeds_when_bitacora_write_fails(self):
        with patch(
            "apps.administracion.services.bitacora_acceso_service.BitacoraAcceso.objects.create",
            side_effect=RuntimeError("db down"),
        ):
            response = self._get(f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=0")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(BitacoraAcceso.objects.exists())

    def test_read_is_logged_even_when_cache_is_down(self):
        with patch(
            "apps.consulta_medica.services.record_access_audit_service.cache.add",
            side_effect=ConnectionError("redis down"),
        ):
            response = self._get(f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=0")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._reads().count(), 1)

    def test_invalid_request_does_not_log_access(self):
        response = self._get(f"/api/v1/patients/{self.no_exp}/clinical-history?pkNum=abc")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertFalse(BitacoraAcceso.objects.exists())

    def test_modifications_are_logged_without_dedup(self):
        url = f"/api/v1/patients/{self.no_exp}/profile?pkNum=0"
        for phone in ("5551111111", "5552222222"):
            self.client.patch(url, {"phone": phone}, format="json", **self._csrf_headers())

        changes = BitacoraAcceso.objects.filter(accion=BitacoraAcceso.Accion.MODIFICAR)
        self.assertEqual(changes.count(), 2)
        self.assertEqual(set(changes.values_list("recurso", flat=True)), {RecordSection.PATIENT_PROFILE})

    def test_report_export_is_logged(self):
        self._create_user_with_role(
            username="report_user", email="report@example.com", password="Report_Export_123456",
            role_code="REPORTES_AUDIT", permissions=["clinico:reportes:read"],
        )
        self._login_as("report_user", "Report_Export_123456")

        response = self.client.get("/api/v1/reportes/consultas/diario?export=xlsx")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = BitacoraAcceso.objects.get(accion=BitacoraAcceso.Accion.EXPORTAR)
        self.assertEqual(entry.recurso, RecordSection.DAILY_REPORT)
        self.assertEqual(entry.cd_usuario, "report_user")
        self.assertIsNone(entry.no_exp)
