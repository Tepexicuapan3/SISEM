import datetime
import io

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Licencias, Permisos, Roles
from apps.consulta_medica.models import MedicalLeave, VisitConsultation
from apps.recepcion.models import Visit


class MedicalLeaveReportApiTests(APITestCase):
    """
    Equivalente moderno de body-repincap.jsp -- ver
    docs/architecture/legacy-reports-inventory.md.
    """

    def setUp(self):
        self.request_id = "66666666-6666-6666-6666-666666666666"
        self.reader_password = "Reader_123456"
        self.no_perm_password = "NoPerm_123456"

        self.reader_user = self._create_user_with_role(
            username="incap_reader",
            email="incap.reader@example.com",
            password=self.reader_password,
            role_code="INCAP_READER",
            permissions=["clinico:reportes:read"],
        )
        self._create_user_with_role(
            username="sin_permiso_incap",
            email="sin.permiso.incap@example.com",
            password=self.no_perm_password,
            role_code="SIN_PERMISO_INCAP",
            permissions=[],
        )

        self.doctor = SyUsuario.objects.create(
            usuario="doctor_incap",
            correo="doctor.incap@example.com",
            clave_hash=make_password("Doctor_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.doctor, nombre="Doctor", paterno="Incap", materno=""
        )

        self.leave_type = Licencias.objects.create(name="Enfermedad General")

        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)

        self.leave_today = self._create_leave(
            folio="INC-0001", no_exp="EXP-I001", visit_folio="VIS-I001",
            start_date=self.today,
        )
        self.leave_yesterday = self._create_leave(
            folio="INC-0002", no_exp="EXP-I002", visit_folio="VIS-I002",
            start_date=self.yesterday,
        )

    def _create_leave(self, *, folio, no_exp, visit_folio, start_date):
        visit = Visit.objects.create(
            folio=visit_folio,
            no_exp=no_exp,
            nombre_paciente=f"Paciente {no_exp}",
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="cerrada",
            doctor=self.doctor,
        )
        consultation = VisitConsultation.objects.create(
            id_visit=visit,
            doctor=self.doctor,
            primary_diagnosis="Diagnostico de prueba",
            final_note="Nota final",
            is_active=True,
        )
        return MedicalLeave.objects.create(
            consultation=consultation,
            no_exp=no_exp,
            pk_num=0,
            leave_type=self.leave_type,
            is_subsequent=False,
            days=3,
            start_date=start_date,
            end_date=start_date + datetime.timedelta(days=2),
            folio=folio,
        )

    def _create_user_with_role(self, username, email, password, role_code, permissions):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=email,
            clave_hash=make_password(password),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="User"
        )
        role, _ = Roles.objects.get_or_create(
            rol=role_code,
            defaults={"desc_rol": f"Rol {role_code}", "landing_route": "/reportes"},
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)

        for permission_code in permissions:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code,
                defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)

        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": username, "password": password},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def test_default_range_is_today_only(self):
        self._login_as("incap_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/incapacidades")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["noExp"], "EXP-I001")
        self.assertEqual(response.data["items"][0]["leaveTypeName"], "Enfermedad General")

    def test_explicit_range_includes_both_days(self):
        self._login_as("incap_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/incapacidades",
            {
                "fechaInicio": self.yesterday.isoformat(),
                "fechaFin": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 2)

    def test_requires_permission(self):
        self._login_as("sin_permiso_incap", self.no_perm_password)

        response = self.client.get("/api/v1/reportes/incapacidades")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")

    def test_invalid_date_range_returns_validation_error(self):
        self._login_as("incap_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/incapacidades",
            {
                "fechaInicio": self.today.isoformat(),
                "fechaFin": self.yesterday.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_filters_by_leave_type_id(self):
        self._login_as("incap_reader", self.reader_password)

        other_type = Licencias.objects.create(name="Maternidad")

        response = self.client.get(
            "/api/v1/reportes/incapacidades", {"leaveTypeId": other_type.id}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 0)

    def test_export_xlsx_returns_workbook(self):
        import openpyxl

        self._login_as("incap_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/incapacidades", {"export": "xlsx"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(rows[0][4], "No. Expediente")
        self.assertEqual(rows[1][4], "EXP-I001")
