"""
Solicitudes ARCO (change `solicitudes-arco`): alta con folio y plazo en dias
habiles, maquina de estatus con resolucion inmutable, auditoria estricta y
separacion de permisos read/write.
"""
from datetime import date, timedelta

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status

from apps.administracion.models import AuditoriaEvento, SolicitudArco
from apps.administracion.use_cases.arco.arco_usecase import add_business_days
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase

ARCO_URL = "/api/v1/solicitudes-arco"


class AddBusinessDaysTests(_ConsultationAuditApiTestBase):
    def test_skips_weekends(self):
        friday = date(2026, 9, 25)
        self.assertEqual(add_business_days(friday, 1), date(2026, 9, 28))
        self.assertEqual(add_business_days(friday, 5), date(2026, 10, 2))
        self.assertEqual(add_business_days(friday, 20), date(2026, 10, 23))


class SolicitudesArcoApiTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.compliance_password = "Compliance_Arco_123456"
        self.reader_password = "Reader_Arco_123456"
        self.compliance_user = self._create_user_with_role(
            username="arco_compliance_user",
            email="arco.compliance@example.com",
            password=self.compliance_password,
            role_code="COMPLIANCE_ARCO",
            permissions=["admin:arco:read", "admin:arco:write"],
        )
        self._create_user_with_role(
            username="arco_reader_user",
            email="arco.reader@example.com",
            password=self.reader_password,
            role_code="LECTOR_ARCO",
            permissions=["admin:arco:read"],
        )

    def _login_compliance(self):
        self._login_as("arco_compliance_user", self.compliance_password)

    def _payload(self, **overrides):
        payload = {
            "type": "A",
            "noExp": "EXPARCO1",
            "pkNum": 0,
            "requesterName": "Juan Perez",
            "requesterEmail": "juan@example.com",
            "description": "Solicito copia de mi expediente clinico.",
            "receivedDate": "2026-09-25",
        }
        payload.update(overrides)
        return payload

    def _create(self, **overrides):
        return self.client.post(
            ARCO_URL, self._payload(**overrides), format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def _change_status(self, solicitud_id, body):
        return self.client.post(
            f"{ARCO_URL}/{solicitud_id}/status", body, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def test_create_assigns_folio_due_date_and_audits(self):
        self._login_compliance()

        response = self._create(transparencyFolio="UT-2026-0099")

        self.assertEqual(response.data["transparencyFolio"], "UT-2026-0099")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        solicitud = SolicitudArco.objects.get()
        self.assertEqual(response.data["folio"], f"ARCO-2026-{solicitud.id_solicitud:06d}")
        self.assertEqual(response.data["status"], "recibida")
        self.assertEqual(response.data["dueDate"], "2026-10-23")
        self.assertEqual(response.data["registeredBy"]["username"], "arco_compliance_user")
        event = AuditoriaEvento.objects.get(accion="ArcoRequestCreated")
        self.assertEqual(event.recurso_tipo, "solicitud_arco")
        self.assertEqual(event.recurso_id, solicitud.id_solicitud)

    @override_settings(ARCO_PLAZO_DIAS_HABILES=10)
    def test_due_date_uses_configured_business_days(self):
        self._login_compliance()

        response = self._create()

        self.assertEqual(response.data["dueDate"], "2026-10-09")

    def test_create_rejects_future_received_date_and_missing_fields(self):
        self._login_compliance()
        tomorrow = (date.today() + timedelta(days=2)).isoformat()

        future = self._create(receivedDate=tomorrow)
        missing = self._create(requesterName="", type="otro")

        self.assertEqual(future.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(missing.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(set(missing.data["details"]), {"requesterName", "type"})
        self.assertFalse(SolicitudArco.objects.exists())

    def test_read_only_user_cannot_create_or_resolve(self):
        self._login_compliance()
        solicitud_id = self._create().data["id"]
        self._login_as("arco_reader_user", self.reader_password)

        listing = self.client.get(ARCO_URL)
        create = self._create()
        resolve = self._change_status(solicitud_id, {"status": "procedente", "response": "Ok"})

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resolve.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_permission_cannot_list(self):
        self._login_doctor()

        response = self.client.get(ARCO_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_lifecycle_and_resolution_is_immutable(self):
        self._login_compliance()
        solicitud_id = self._create().data["id"]

        in_progress = self._change_status(solicitud_id, {"status": "en_proceso"})
        resolved = self._change_status(
            solicitud_id, {"status": "procedente", "response": "Se entrega copia."},
        )
        reopen = self._change_status(
            solicitud_id, {"status": "improcedente", "response": "Cambio de opinion"},
        )

        self.assertEqual(in_progress.data["status"], "en_proceso")
        self.assertEqual(resolved.data["status"], "procedente")
        self.assertEqual(resolved.data["response"], "Se entrega copia.")
        self.assertEqual(resolved.data["resolvedBy"]["username"], "arco_compliance_user")
        # SOLICITUD_ARCO.fe_respuesta del documento.
        self.assertIsNotNone(resolved.data["responseDate"])
        self.assertEqual(reopen.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(reopen.data["code"], "ARCO_ALREADY_RESOLVED")
        transitions = [
            (e.datos_antes["estatus"], e.datos_despues["estatus"])
            for e in AuditoriaEvento.objects.filter(accion="ArcoRequestStatusChanged").order_by("id_evento")
        ]
        self.assertEqual(transitions, [("recibida", "en_proceso"), ("en_proceso", "procedente")])

    def test_resolution_requires_response(self):
        self._login_compliance()
        solicitud_id = self._create().data["id"]

        response = self._change_status(solicitud_id, {"status": "improcedente", "response": "  "})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(SolicitudArco.objects.get().estatus, "recibida")

    def test_cannot_move_back_to_in_progress(self):
        self._login_compliance()
        solicitud_id = self._create().data["id"]
        self._change_status(solicitud_id, {"status": "en_proceso"})

        response = self._change_status(solicitud_id, {"status": "en_proceso"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "INVALID_TRANSITION")

    def test_status_change_rolls_back_when_audit_fails(self):
        self._login_compliance()
        solicitud_id = self._create().data["id"]

        response = self._call_with_audit_down(
            lambda: self._change_status(solicitud_id, {"status": "procedente", "response": "Ok"})
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(SolicitudArco.objects.get().estatus, "recibida")

    def test_unknown_solicitud_returns_404(self):
        self._login_compliance()

        detail = self.client.get(f"{ARCO_URL}/999")
        change = self._change_status(999, {"status": "en_proceso"})

        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(change.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_filters_by_status_patient_and_overdue(self):
        self._login_compliance()
        old_id = self._create(receivedDate="2026-01-05").data["id"]
        self._create(noExp="EXPARCO2", receivedDate=date.today().isoformat())
        resolved_old_id = self._create(receivedDate="2026-01-05").data["id"]
        self._change_status(resolved_old_id, {"status": "improcedente", "response": "No aplica"})

        overdue = self.client.get(ARCO_URL, {"vencidas": "true"})
        by_patient = self.client.get(ARCO_URL, {"noExp": "EXPARCO2"})
        by_status = self.client.get(ARCO_URL, {"estatus": "improcedente"})
        invalid = self.client.get(ARCO_URL, {"estatus": "x"})

        self.assertEqual([item["id"] for item in overdue.data["items"]], [old_id])
        self.assertTrue(overdue.data["items"][0]["isOverdue"])
        self.assertEqual(by_patient.data["total"], 1)
        self.assertEqual(by_status.data["total"], 1)
        self.assertEqual(invalid.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
