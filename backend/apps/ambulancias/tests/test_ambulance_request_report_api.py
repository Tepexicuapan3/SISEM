import io

import openpyxl
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.ambulancias.models import AmbulanceRequest
from apps.catalogos.models import CatDestinoAmbulancia, CatMotivoTraslado, Permisos, Roles

from ._clinic_mock import mock_clinic


class AmbulanceRequestReportApiTests(APITestCase):
    def setUp(self):
        self.request_id = "10101010-1010-1010-1010-101010101010"
        self.reader_password = "Reader_123456"

        self._create_user_with_role(
            username="ambulancias_reader",
            email="ambulancias.reader@example.com",
            password=self.reader_password,
            role_code="AMBULANCIAS_READER",
            permissions=["clinico:ambulancias:read"],
        )

        self.clinic_id = mock_clinic(self)
        self.reason = CatMotivoTraslado.objects.create(name="Consulta de especialidad")
        self.destination = CatDestinoAmbulancia.objects.create(name="Hospital Regional")

        AmbulanceRequest.objects.create(
            folio="AMB-0002", no_exp="EXP-A200", requesting_clinic_id=self.clinic_id,
            requested_by_name="Ana Diaz", reason=self.reason, destination=self.destination,
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

    def test_default_range_is_today_only(self):
        self._login_as("ambulancias_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/ambulancias")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["noExp"], "EXP-A200")

    def test_export_xlsx_returns_workbook(self):
        self._login_as("ambulancias_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/ambulancias", {"export": "xlsx"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(rows[0][2], "No. Expediente")
        self.assertEqual(rows[1][2], "EXP-A200")
