"""
Suite de auditoria de `ambulancias` (Fase 6.2 del change
`auditoria-cirugias-ambulancias`, engram #514).

Cubre las 4 acciones de auditoria de este dominio:
- `AmbulanceRequestCreated` (SIMPLE): evento correcto + persiste aunque
  falle la auditoria.
- `AmbulanceRequestAuthorized` / `Rejected` / `Cancelled` (ESTRICTO):
  evento correcto + rollback si falla el `audit_hook` + guarda de estado
  ya-resuelto no crea eventos huerfanos.

`setUp` clonado de `test_ambulance_request_authorize_api.py` +
`mock_clinic(self)` OBLIGATORIO (`_clinic_mock.py:31`): `CatClinica` vive
en la BD "expedientes" (managed=False, alias inexistente bajo
`manage.py test`), por lo que `requestingClinicId`/`to_contract` deben
simularse con el mock en vez de una fila real.
"""
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.ambulancias.models import AmbulanceRequest, AmbulanceRequestSchedule
from apps.catalogos.models import (
    CatDestinoAmbulancia, CatMotivoTraslado, CatTipoServicioAmbulancia,
    CatTipoTraslado, Permisos, Roles,
)

from ._clinic_mock import mock_clinic


class AmbulanceRequestAuditApiTests(APITestCase):
    def setUp(self):
        self.request_id = "77777777-7777-7777-7777-777777777777"
        self.writer_password = "Writer_123456"
        self.authorizer_password = "Authorizer_123456"

        self._create_user_with_role(
            username="ambulancias_audit_writer",
            email="ambulancias.audit.writer@example.com",
            password=self.writer_password,
            role_code="AMBULANCIAS_AUDIT_WRITER",
            permissions=["clinico:ambulancias:write", "clinico:ambulancias:read"],
        )
        self._create_user_with_role(
            username="ambulancias_audit_authorizer",
            email="ambulancias.audit.authorizer@example.com",
            password=self.authorizer_password,
            role_code="AMBULANCIAS_AUDIT_AUTHORIZER",
            permissions=["clinico:ambulancias:authorize", "clinico:ambulancias:read"],
        )

        self.clinic_id = mock_clinic(self)
        self.reason = CatMotivoTraslado.objects.create(name="Consulta de especialidad")
        self.destination = CatDestinoAmbulancia.objects.create(name="Hospital Regional")
        self.transfer_type = CatTipoTraslado.objects.create(name="Ida y vuelta")
        self.service_type = CatTipoServicioAmbulancia.objects.create(name="Basica")

    def _create_user_with_role(self, username, email, password, role_code, permissions):
        user = SyUsuario.objects.create(
            usuario=username, correo=email, clave_hash=make_password(password),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        role, _ = Roles.objects.get_or_create(
            rol=role_code, defaults={"desc_rol": f"Rol {role_code}", "landing_route": "/reportes"},
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for permission_code in permissions:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code, defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": password},
            format="json", HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _create_payload(self, **overrides):
        payload = {
            "noExp": "EXP-A200",
            "requestingClinicId": self.clinic_id,
            "requestedByName": "Maria Perez",
            "reasonId": self.reason.id,
            "destinationId": self.destination.id,
            "schedules": [
                {
                    "transferDate": "2026-01-02",
                    "transferTime": "08:00:00",
                    "transferTypeId": self.transfer_type.id,
                    "serviceTypeId": self.service_type.id,
                },
                {
                    "transferDate": "2026-01-05",
                    "transferTime": "09:00:00",
                    "transferTypeId": self.transfer_type.id,
                    "serviceTypeId": self.service_type.id,
                },
            ],
        }
        payload.update(overrides)
        return payload

    def _make_request(self):
        request = AmbulanceRequest.objects.create(
            folio="AMB-AUDIT-0001", no_exp="EXP-A201", requesting_clinic_id=self.clinic_id,
            requested_by_name="Juan Lopez", reason=self.reason, destination=self.destination,
        )
        AmbulanceRequestSchedule.objects.create(
            request=request, transfer_date="2026-01-02", transfer_time="08:00:00",
            transfer_type=self.transfer_type, service_type=self.service_type,
        )
        return request

    # ------------------------------------------------------------------
    # AmbulanceRequestCreated (SIMPLE)
    # ------------------------------------------------------------------

    def test_create_writes_audit_event(self):
        self._login_as("ambulancias_audit_writer", self.writer_password)

        response = self.client.post(
            "/api/v1/ambulance-requests", self._create_payload(), format="json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        events = AuditoriaEvento.objects.filter(accion="AmbulanceRequestCreated")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_tipo, "ambulancias")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["authorizationStatus"], "pendiente")
        self.assertEqual(event.datos_despues["schedulesCount"], 2)
        self.assertEqual(event.datos_despues["reasonId"], self.reason.id)
        self.assertEqual(event.datos_despues["destinationId"], self.destination.id)
        self.assertEqual(event.datos_despues["requestingClinicId"], self.clinic_id)
        self.assertEqual(event.meta["module"], "ambulancias")

    def test_create_persists_even_if_audit_fails(self):
        self._login_as("ambulancias_audit_writer", self.writer_password)

        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            response = self.client.post(
                "/api/v1/ambulance-requests", self._create_payload(), format="json",
                **self._csrf_headers(),
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AmbulanceRequest.objects.filter(folio=response.data["folio"]).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="AmbulanceRequestCreated").count(), 0)

    # ------------------------------------------------------------------
    # AmbulanceRequestAuthorized (ESTRICTO)
    # ------------------------------------------------------------------

    def test_authorize_writes_audit_event(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_authorizer", self.authorizer_password)

        response = self.client.patch(
            f"/api/v1/ambulance-requests/{ambulance_request.id}/authorize",
            {"serviceNumber": "AMB-01"}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        events = AuditoriaEvento.objects.filter(accion="AmbulanceRequestAuthorized")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_tipo, "ambulancias")
        self.assertEqual(event.recurso_id, ambulance_request.id)
        self.assertEqual(
            event.datos_antes, {"authorizationStatus": "pendiente", "serviceNumber": None},
        )
        self.assertEqual(event.datos_despues["authorizationStatus"], "autorizada")
        self.assertEqual(event.datos_despues["serviceNumber"], "AMB-01")
        self.assertIsInstance(event.datos_despues["authorizedAt"], str)

    def test_authorize_audit_failure_rolls_back(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_authorizer", self.authorizer_password)

        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            response = self.client.patch(
                f"/api/v1/ambulance-requests/{ambulance_request.id}/authorize",
                {"serviceNumber": "AMB-01"}, format="json", **self._csrf_headers(),
            )

        self.assertEqual(response.status_code, 500)
        ambulance_request.refresh_from_db()
        self.assertEqual(ambulance_request.authorization_status, AmbulanceRequest.AuthorizationStatus.PENDIENTE)
        self.assertIsNone(ambulance_request.service_number)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="AmbulanceRequestAuthorized").count(), 0)

    # ------------------------------------------------------------------
    # AmbulanceRequestRejected (ESTRICTO)
    # ------------------------------------------------------------------

    def test_reject_writes_audit_event(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_authorizer", self.authorizer_password)

        response = self.client.patch(
            f"/api/v1/ambulance-requests/{ambulance_request.id}/reject",
            {"notes": "No cumple criterios"}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        events = AuditoriaEvento.objects.filter(accion="AmbulanceRequestRejected")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_id, ambulance_request.id)
        self.assertEqual(event.datos_antes, {"authorizationStatus": "pendiente"})
        self.assertEqual(event.datos_despues["authorizationStatus"], "rechazada")
        self.assertEqual(event.datos_despues["rejectionNotes"], "No cumple criterios")
        self.assertIsInstance(event.datos_despues["authorizedAt"], str)

    def test_reject_audit_failure_rolls_back(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_authorizer", self.authorizer_password)

        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            response = self.client.patch(
                f"/api/v1/ambulance-requests/{ambulance_request.id}/reject",
                {"notes": "No cumple criterios"}, format="json", **self._csrf_headers(),
            )

        self.assertEqual(response.status_code, 500)
        ambulance_request.refresh_from_db()
        self.assertEqual(ambulance_request.authorization_status, AmbulanceRequest.AuthorizationStatus.PENDIENTE)
        self.assertIsNone(ambulance_request.authorized_at)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="AmbulanceRequestRejected").count(), 0)

    # ------------------------------------------------------------------
    # AmbulanceRequestCancelled (ESTRICTO)
    # ------------------------------------------------------------------

    def test_cancel_writes_audit_event(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_writer", self.writer_password)

        response = self.client.patch(
            f"/api/v1/ambulance-requests/{ambulance_request.id}/cancel", {}, format="json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        events = AuditoriaEvento.objects.filter(accion="AmbulanceRequestCancelled")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_id, ambulance_request.id)
        self.assertEqual(event.datos_antes, {"status": "activa"})
        self.assertEqual(event.datos_despues, {"status": "baja"})

    def test_cancel_audit_failure_rolls_back(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_writer", self.writer_password)

        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            response = self.client.patch(
                f"/api/v1/ambulance-requests/{ambulance_request.id}/cancel", {}, format="json",
                **self._csrf_headers(),
            )

        self.assertEqual(response.status_code, 500)
        ambulance_request.refresh_from_db()
        self.assertEqual(ambulance_request.status, AmbulanceRequest.Status.ACTIVA)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="AmbulanceRequestCancelled").count(), 0)

    # ------------------------------------------------------------------
    # Guarda de estado ya-resuelto/cancelado
    # ------------------------------------------------------------------

    def test_already_resolved_guard_writes_no_event(self):
        ambulance_request = self._make_request()
        self._login_as("ambulancias_audit_authorizer", self.authorizer_password)

        first = self.client.patch(
            f"/api/v1/ambulance-requests/{ambulance_request.id}/authorize",
            {"serviceNumber": "AMB-01"}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="AmbulanceRequestAuthorized").count(), 1)

        second = self.client.patch(
            f"/api/v1/ambulance-requests/{ambulance_request.id}/authorize",
            {"serviceNumber": "AMB-02"}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        # La guarda dispara antes del hook -- el conteo NO sube del intento previo.
        self.assertEqual(AuditoriaEvento.objects.filter(accion="AmbulanceRequestAuthorized").count(), 1)
