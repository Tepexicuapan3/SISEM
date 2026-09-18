from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import (
    CatDestinoAmbulancia, CatMotivoTraslado, CatTipoServicioAmbulancia,
    CatTipoTraslado, Permisos, Roles,
)

from ._clinic_mock import mock_clinic


class AmbulanceRequestCreateApiTests(APITestCase):
    def setUp(self):
        self.request_id = "88888888-8888-8888-8888-888888888888"
        self.writer_password = "Writer_123456"

        self._create_user_with_role(
            username="ambulancias_writer",
            email="ambulancias.writer@example.com",
            password=self.writer_password,
            role_code="AMBULANCIAS_WRITER",
            permissions=["clinico:ambulancias:write", "clinico:ambulancias:read"],
        )

        self.clinic_id = mock_clinic(self)
        self.reason = CatMotivoTraslado.objects.create(name="Consulta de especialidad", requires_notes=False)
        self.reason_other = CatMotivoTraslado.objects.create(name="Otro", requires_notes=True)
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

    def _payload(self, **overrides):
        payload = {
            "noExp": "EXP-A001",
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
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_create_request_with_multiple_schedules_succeeds(self):
        self._login_as("ambulancias_writer", self.writer_password)

        payload = self._payload(schedules=[
            {"transferDate": "2026-01-02", "transferTime": "08:00:00",
             "transferTypeId": self.transfer_type.id, "serviceTypeId": self.service_type.id},
            {"transferDate": "2026-01-05", "transferTime": "09:00:00",
             "transferTypeId": self.transfer_type.id, "serviceTypeId": self.service_type.id},
        ])

        response = self.client.post(
            "/api/v1/ambulance-requests", payload, format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["schedules"]), 2)
        self.assertEqual(response.data["authorizationStatus"], "pendiente")
        self.assertTrue(response.data["folio"].startswith("AMB-"))

    def test_reason_other_without_notes_fails(self):
        self._login_as("ambulancias_writer", self.writer_password)

        payload = self._payload(reasonId=self.reason_other.id)

        response = self.client.post(
            "/api/v1/ambulance-requests", payload, format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("reasonNotes", response.data["details"])

    def test_reason_other_with_notes_succeeds(self):
        self._login_as("ambulancias_writer", self.writer_password)

        payload = self._payload(reasonId=self.reason_other.id, reasonNotes="Traslado especial")

        response = self.client.post(
            "/api/v1/ambulance-requests", payload, format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_missing_schedules_fails(self):
        self._login_as("ambulancias_writer", self.writer_password)

        payload = self._payload(schedules=[])

        response = self.client.post(
            "/api/v1/ambulance-requests", payload, format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
