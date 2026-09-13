import datetime
import io

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Especialidades, Permisos, Roles
from apps.consulta_medica.models import VisitConsultation
from apps.pases.models import Referral
from apps.recepcion.models import Visit


class ReferralReportApiTests(APITestCase):
    """
    Equivalente moderno de body-repases.jsp/body-repingresados.jsp/
    body-rephospital.jsp -- ver docs/architecture/legacy-reports-inventory.md.
    """

    def setUp(self):
        self.request_id = "55555555-5555-5555-5555-555555555555"
        self.reader_password = "Reader_123456"
        self.no_perm_password = "NoPerm_123456"

        self.reader_user = self._create_user_with_role(
            username="pases_reader",
            email="pases.reader@example.com",
            password=self.reader_password,
            role_code="PASES_READER",
            permissions=["clinico:pases:read"],
        )
        self._create_user_with_role(
            username="sin_permiso_pases",
            email="sin.permiso.pases@example.com",
            password=self.no_perm_password,
            role_code="SIN_PERMISO_PASES",
            permissions=[],
        )

        self.doctor = SyUsuario.objects.create(
            usuario="doctor_pases",
            correo="doctor.pases@example.com",
            clave_hash=make_password("Doctor_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.doctor, nombre="Doctor", paterno="Pases", materno=""
        )

        self.especialidad = Especialidades.objects.create(name="Cardiología")
        self.centro = CatCentroAtencion.objects.create(
            name="Hospital Central",
            code="HC-001",
            center_type=CatCentroAtencion.TipoCentro.HOSPITAL,
            is_external=False,
            address="Av. Siempre Viva 1",
            is_active=True,
            created_by_id=self.doctor.id_usuario,
        )

        self.today = datetime.date.today()
        self.yesterday = self.today - datetime.timedelta(days=1)

        self.referral_today = self._create_referral(
            folio="PASE-0001",
            no_exp="EXP-P001",
            visit_folio="VIS-P001",
            referral_type=Referral.ReferralType.ESPECIALIDAD,
            destination_center=self.centro,
            specialty=self.especialidad,
            created_at=self.today,
        )
        self.referral_yesterday = self._create_referral(
            folio="PASE-0002",
            no_exp="EXP-P002",
            visit_folio="VIS-P002",
            referral_type=Referral.ReferralType.LABORATORIO,
            destination_center=None,
            specialty=None,
            created_at=self.yesterday,
        )

    def _create_referral(
        self,
        *,
        folio,
        no_exp,
        visit_folio,
        referral_type,
        destination_center,
        specialty,
        created_at,
    ):
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
        referral = Referral.objects.create(
            consultation=consultation,
            no_exp=no_exp,
            pk_num=0,
            referral_type=referral_type,
            destination_center=destination_center,
            specialty=specialty,
            folio=folio,
        )
        # created_at es auto_now_add -- se ajusta despues via update() para
        # simular un pase de un dia distinto sin tocar la logica del modelo.
        Referral.objects.filter(pk=referral.pk).update(
            created_at=datetime.datetime.combine(created_at, datetime.time(8, 0))
        )
        referral.refresh_from_db()
        return referral

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
        self._login_as("pases_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/pases")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["noExp"], "EXP-P001")
        self.assertEqual(
            response.data["items"][0]["destinationCenterName"], "Hospital Central"
        )
        self.assertEqual(response.data["items"][0]["specialtyName"], "Cardiología")

    def test_explicit_range_includes_both_days(self):
        self._login_as("pases_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/pases",
            {
                "fechaInicio": self.yesterday.isoformat(),
                "fechaFin": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 2)

    def test_filters_by_referral_type(self):
        self._login_as("pases_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/pases",
            {
                "fechaInicio": self.yesterday.isoformat(),
                "fechaFin": self.today.isoformat(),
                "tipoPase": Referral.ReferralType.LABORATORIO,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["noExp"], "EXP-P002")

    def test_invalid_referral_type_returns_validation_error(self):
        self._login_as("pases_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/pases", {"tipoPase": "no_existe"}
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_requires_permission(self):
        self._login_as("sin_permiso_pases", self.no_perm_password)

        response = self.client.get("/api/v1/reportes/pases")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")

    def test_invalid_date_range_returns_validation_error(self):
        self._login_as("pases_reader", self.reader_password)

        response = self.client.get(
            "/api/v1/reportes/pases",
            {
                "fechaInicio": self.today.isoformat(),
                "fechaFin": self.yesterday.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_export_xlsx_returns_workbook(self):
        import openpyxl

        self._login_as("pases_reader", self.reader_password)

        response = self.client.get("/api/v1/reportes/pases", {"export": "xlsx"})

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
        self.assertEqual(rows[1][3], "EXP-P001")
