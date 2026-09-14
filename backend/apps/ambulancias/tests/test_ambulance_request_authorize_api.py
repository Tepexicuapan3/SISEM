from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.ambulancias.models import AmbulanceRequest, AmbulanceRequestSchedule
from apps.catalogos.models import (
    CatDestinoAmbulancia, CatMotivoTraslado, CatTipoServicioAmbulancia,
    CatTipoTraslado, Permisos, Roles,
)

from ._clinic_mock import mock_clinic


class AmbulanceRequestAuthorizeApiTests(APITestCase):
    def setUp(self):
        self.request_id = "99999999-9999-9999-9999-999999999999"
        self.writer_password = "Writer_123456"
        self.authorizer_password = "Authorizer_123456"

        self._create_user_with_role(
            username="ambulancias_writer2",
            email="ambulancias.writer2@example.com",
            password=self.writer_password,
            role_code="AMBULANCIAS_WRITER2",
            permissions=["clinico:ambulancias:write", "clinico:ambulancias:read"],
        )
        self._create_user_with_role(
            username="ambulancias_authorizer",
            email="ambulancias.authorizer@example.com",
            password=self.authorizer_password,
            role_code="AMBULANCIAS_AUTHORIZER",
            permissions=["clinico:ambulancias:authorize", "clinico:ambulancias:read"],
        )

        self.clinic_id = mock_clinic(self)
        self.reason = CatMotivoTraslado.objects.create(name="Consulta de especialidad")
        self.destination = CatDestinoAmbulancia.objects.create(name="Hospital Regional")
        self.transfer_type = CatTipoTraslado.objects.create(name="Ida y vuelta")
        self.service_type = CatTipoServicioAmbulancia.objects.create(name="Basica")

        self.ambulance_request = AmbulanceRequest.objects.create(
            folio="AMB-0001", no_exp="EXP-A100", requesting_clinic_id=self.clinic_id,
            requested_by_name="Juan Lopez", reason=self.reason, destination=self.destination,
        )
        AmbulanceRequestSchedule.objects.create(
            request=self.ambulance_request, transfer_date="2026-01-02", transfer_time="08:00:00",
            transfer_type=self.transfer_type, service_type=self.service_type,
        )

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

    def test_write_permission_alone_cannot_authorize(self):
        self._login_as("ambulancias_writer2", self.writer_password)

        response = self.client.patch(
            f"/api/v1/ambulance-requests/{self.ambulance_request.id}/authorize",
            {"serviceNumber": "AMB-01"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorize_without_service_number_fails(self):
        self._login_as("ambulancias_authorizer", self.authorizer_password)

        response = self.client.patch(
            f"/api/v1/ambulance-requests/{self.ambulance_request.id}/authorize",
            {}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_authorize_succeeds_and_cannot_repeat(self):
        self._login_as("ambulancias_authorizer", self.authorizer_password)

        first = self.client.patch(
            f"/api/v1/ambulance-requests/{self.ambulance_request.id}/authorize",
            {"serviceNumber": "AMB-01"}, format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["authorizationStatus"], "autorizada")
        self.assertEqual(first.data["serviceNumber"], "AMB-01")

        second = self.client.patch(
            f"/api/v1/ambulance-requests/{self.ambulance_request.id}/authorize",
            {"serviceNumber": "AMB-02"}, format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_reject_requires_notes(self):
        self._login_as("ambulancias_authorizer", self.authorizer_password)

        missing_notes = self.client.patch(
            f"/api/v1/ambulance-requests/{self.ambulance_request.id}/reject", {}, format="json",
        )
        self.assertEqual(missing_notes.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        rejected = self.client.patch(
            f"/api/v1/ambulance-requests/{self.ambulance_request.id}/reject",
            {"notes": "No cumple criterios"}, format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.data["authorizationStatus"], "rechazada")
