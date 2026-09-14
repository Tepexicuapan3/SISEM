import datetime
import io

import openpyxl
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatClasificacionCirugia, CatTipoCirugia, Permisos, Roles
from apps.cirugias.models import SurgerySchedule
from apps.medicos.models import CatMedico


class SurgeryReportApiTests(APITestCase):
    def setUp(self):
        self.request_id = "77777777-7777-7777-7777-777777777777"
        self.reader_password = "Reader_123456"

        self._create_user_with_role(
            username="cirugias_reader",
            email="cirugias.reader@example.com",
            password=self.reader_password,
            role_code="CIRUGIAS_READER",
            permissions=["clinico:cirugias:read"],
        )

        self.surgeon = CatMedico.objects.create(nombre_display="Dr. Reporte")
        self.surgery_type = CatTipoCirugia.objects.create(name="Colecistectomia")
        self.classification = CatClasificacionCirugia.objects.create(name="Cirugia de quirofano")

        self.today = datetime.date.today()
        SurgerySchedule.objects.create(
            folio="CIR-0001", no_exp="EXP-R001", pk_num=0,
            surgeon=self.surgeon, surgery_type=self.surgery_type,
            classification=self.classification,
            scheduled_date=self.today, scheduled_time=datetime.time(10, 0),
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
        self._login_as("cirugias_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/cirugias")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["noExp"], "EXP-R001")

    def test_export_xlsx_returns_workbook(self):
        self._login_as("cirugias_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/cirugias", {"export": "xlsx"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(rows[0][3], "No. Expediente")
        self.assertEqual(rows[1][3], "EXP-R001")
