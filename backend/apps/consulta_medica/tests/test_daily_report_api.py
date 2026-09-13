import datetime
import io

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies, Permisos, Roles
from apps.consulta_medica.models import VisitConsultation
from apps.recepcion.models import Visit


class DailyConsultationReportApiTests(APITestCase):
    """
    Equivalente moderno de body-repconsulta.jsp ("Informe Diario de Consulta
    Medica") -- ver docs/architecture/legacy-reports-inventory.md.
    """

    def setUp(self):
        self.request_id = "44444444-4444-4444-4444-444444444444"
        self.reader_password = "Reader_123456"
        self.no_perm_password = "NoPerm_123456"

        self.reader_user = self._create_user_with_role(
            username="reportes_reader",
            email="reportes.reader@example.com",
            password=self.reader_password,
            role_code="REPORTES_READER",
            permissions=["clinico:reportes:read"],
        )
        self._create_user_with_role(
            username="sin_permiso",
            email="sin.permiso@example.com",
            password=self.no_perm_password,
            role_code="SIN_PERMISO_REPORTES",
            permissions=[],
        )

        self.doctor = SyUsuario.objects.create(
            usuario="doctor_reportes",
            correo="doctor.reportes@example.com",
            clave_hash=make_password("Doctor_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.doctor, nombre="Doctor", paterno="Reportes", materno=""
        )

        self.cie = CatCies.objects.create(
            code="A090",
            description="GASTROENTERITIS",
            version="CIE-10",
            is_active=True,
        )

        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)

        self.visit_today = Visit.objects.create(
            folio="REP-0001",
            no_exp="EXP-0001",
            nombre_paciente="Paciente De Hoy",
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="cerrada",
            fecha_consulta=self.today,
            hora_consulta=datetime.time(9, 0),
            doctor=self.doctor,
        )
        VisitConsultation.objects.create(
            id_visit=self.visit_today,
            doctor=self.doctor,
            primary_diagnosis="Gastroenteritis aguda",
            cie=self.cie,
            final_note="Nota final de hoy",
            is_active=True,
        )

        self.visit_yesterday = Visit.objects.create(
            folio="REP-0002",
            no_exp="EXP-0002",
            nombre_paciente="Paciente De Ayer",
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="cerrada",
            fecha_consulta=self.yesterday,
            hora_consulta=datetime.time(10, 0),
            doctor=self.doctor,
        )
        VisitConsultation.objects.create(
            id_visit=self.visit_yesterday,
            doctor=self.doctor,
            primary_diagnosis="Consulta de ayer",
            final_note="Nota final de ayer",
            is_active=True,
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
        self._login_as("reportes_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/consultas/diario")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["noExp"], "EXP-0001")
        self.assertEqual(response.data["items"][0]["cieCode"], "A090")
        self.assertEqual(response.data["items"][0]["doctorName"], "Doctor Reportes")

    def test_explicit_range_includes_both_days(self):
        self._login_as("reportes_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/consultas/diario",
            {
                "fechaInicio": self.yesterday.isoformat(),
                "fechaFin": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 2)
        no_exps = {item["noExp"] for item in response.data["items"]}
        self.assertEqual(no_exps, {"EXP-0001", "EXP-0002"})

    def test_requires_permission(self):
        self._login_as("sin_permiso", self.no_perm_password)

        response = self.client.get("/api/v1/reportes/consultas/diario")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")

    def test_invalid_date_range_returns_validation_error(self):
        self._login_as("reportes_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/consultas/diario",
            {
                "fechaInicio": self.today.isoformat(),
                "fechaFin": self.yesterday.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_invalid_date_format_returns_validation_error(self):
        self._login_as("reportes_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/consultas/diario",
            {"fechaInicio": "not-a-date"},
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_export_xlsx_returns_workbook(self):
        import openpyxl

        self._login_as("reportes_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/consultas/diario", {"export": "xlsx"}
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
        self.assertEqual(rows[0][3], "No. Expediente")
        self.assertEqual(rows[1][3], "EXP-0001")

    def test_filters_by_doctor_id(self):
        self._login_as("reportes_reader", self.reader_password)

        other_doctor = SyUsuario.objects.create(
            usuario="otro_doctor",
            correo="otro.doctor@example.com",
            clave_hash=make_password("Otro_123456"),
            est_activo=True,
        )

        response = self.client.get(
            "/api/v1/reportes/consultas/diario",
            {"doctorId": other_doctor.id_usuario},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 0)
