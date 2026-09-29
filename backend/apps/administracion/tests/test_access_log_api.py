"""
`GET /api/v1/bitacora-acceso`: consulta de BITACORA_ACCESO (tabla propia),
gateada por `admin:auditoria:accesos:read`.
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from apps.administracion.models import BitacoraAcceso
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase

ACCESS_LOG_URL = "/api/v1/bitacora-acceso"


class AccessLogApiTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.auditor_password = "Auditor_Access_123456"
        self.auditor_user = self._create_user_with_role(
            username="access_auditor_user",
            email="access.auditor@example.com",
            password=self.auditor_password,
            role_code="CALIDAD_AUDIT",
            permissions=["admin:auditoria:accesos:read"],
        )

        now = timezone.now()
        self._entry("ver", "EXP1", 0, "historia_clinica", now)
        self._entry("ver", "EXP1", 1, "alergias", now - timedelta(minutes=1))
        self._entry("ver", "EXP2", 0, "consultas", now - timedelta(days=10))
        self._entry("ver", "EXP1", 0, "consultas", now - timedelta(minutes=2), restringidos=2)
        self._entry("modificar", "EXP1", 0, "ficha_paciente", now - timedelta(minutes=3))
        self._entry("exportar", None, None, "reporte_consultas_diario", now - timedelta(minutes=4))

    def _entry(self, accion, no_exp, pk_num, recurso, occurred_at, restringidos=0):
        entry = BitacoraAcceso.objects.create(
            accion=accion, no_exp=no_exp, tp_paciente=pk_num, recurso=recurso,
            usuario=self.doctor_user, cd_usuario=self.doctor_user.usuario,
            ip_origen="10.0.0.1", endpoint="/x", restringidos=restringidos,
        )
        BitacoraAcceso.objects.filter(pk=entry.pk).update(fecha_hora=occurred_at)
        return entry

    def _login_auditor(self):
        self._login_as("access_auditor_user", self.auditor_password)

    def test_requires_access_log_permission(self):
        self._login_doctor()

        response = self.client.get(ACCESS_LOG_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lists_entries_newest_first(self):
        self._login_auditor()

        response = self.client.get(ACCESS_LOG_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 6)
        first = response.data["items"][0]
        self.assertEqual(first["section"], "historia_clinica")
        self.assertEqual(first["action"], "ver")
        self.assertEqual(first["actorUsername"], "audit_doctor_user")
        self.assertEqual(first["actorName"], "audit_doctor_user Test User")
        self.assertEqual(first["ipAddress"], "10.0.0.1")

    def test_filters_by_patient_and_family_member(self):
        self._login_auditor()

        response = self.client.get(ACCESS_LOG_URL, {"noExp": "EXP1", "pkNum": 1})

        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["section"], "alergias")

    def test_filters_by_event_type_and_action(self):
        self._login_auditor()

        restricted = self.client.get(ACCESS_LOG_URL, {"tipo": "diagnostico_restringido"})
        changes = self.client.get(ACCESS_LOG_URL, {"accion": "modificar"})
        exports = self.client.get(ACCESS_LOG_URL, {"accion": "exportar"})

        self.assertEqual(restricted.data["total"], 1)
        self.assertEqual(restricted.data["items"][0]["redactedCount"], 2)
        self.assertEqual(changes.data["items"][0]["section"], "ficha_paciente")
        self.assertIsNone(exports.data["items"][0]["noExp"])

    def test_filters_by_date_range_and_section(self):
        self._login_auditor()
        today = timezone.localdate().isoformat()

        by_date = self.client.get(ACCESS_LOG_URL, {"fechaInicio": today, "fechaFin": today})
        by_section = self.client.get(ACCESS_LOG_URL, {"seccion": "consultas"})

        self.assertEqual(by_date.data["total"], 5)
        self.assertEqual(by_section.data["total"], 2)

    def test_paginates(self):
        self._login_auditor()

        response = self.client.get(ACCESS_LOG_URL, {"page": 2, "pageSize": 4})

        self.assertEqual(response.data["totalPages"], 2)
        self.assertEqual(len(response.data["items"]), 2)

    def test_rejects_invalid_filters(self):
        self._login_auditor()

        response = self.client.get(
            ACCESS_LOG_URL,
            {"tipo": "otro", "accion": "borrar", "fechaInicio": "2026-13-01", "pkNum": "x"},
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(set(response.data["details"]), {"tipo", "accion", "fechaInicio", "pkNum"})
