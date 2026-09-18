import datetime

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatClasificacionCirugia, CatTipoCirugia, Permisos, Roles
from apps.cirugias.models import SurgerySchedule
from apps.medicos.models import CatMedico


class SurgeryScheduleApiTests(APITestCase):
    def setUp(self):
        self.request_id = "66666666-6666-6666-6666-666666666666"
        self.writer_password = "Writer_123456"
        self.no_perm_password = "NoPerm_123456"

        self._create_user_with_role(
            username="cirugias_writer",
            email="cirugias.writer@example.com",
            password=self.writer_password,
            role_code="CIRUGIAS_WRITER",
            permissions=["clinico:cirugias:write", "clinico:cirugias:read"],
        )
        self._create_user_with_role(
            username="sin_permiso_cirugias",
            email="sin.permiso.cirugias@example.com",
            password=self.no_perm_password,
            role_code="SIN_PERMISO_CIRUGIAS",
            permissions=[],
        )

        self.surgeon = CatMedico.objects.create(nombre_display="Dr. Prueba")
        self.surgery_type = CatTipoCirugia.objects.create(name="Apendicectomia")
        self.classification = CatClasificacionCirugia.objects.create(name="Cirugia corta")

        self.tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

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
            "noExp": "EXP-C001",
            "pkNum": 0,
            "surgeonId": self.surgeon.id,
            "surgeryTypeId": self.surgery_type.id,
            "classificationId": self.classification.id,
            "scheduledDate": self.tomorrow,
            "scheduledTime": "09:00:00",
            "durationMinutes": 60,
        }
        payload.update(overrides)
        return payload

    def test_schedule_surgery_succeeds_with_permission(self):
        self._login_as("cirugias_writer", self.writer_password)

        response = self.client.post(
            "/api/v1/surgeries", self._payload(), format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["noExp"], "EXP-C001")
        self.assertEqual(response.data["status"], SurgerySchedule.Status.ACTIVA)
        self.assertTrue(response.data["folio"].startswith("CIR-"))

    def test_schedule_surgery_requires_permission(self):
        self._login_as("sin_permiso_cirugias", self.no_perm_password)

        response = self.client.post(
            "/api/v1/surgeries", self._payload(), format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")

    def test_double_booking_same_surgeon_same_slot_fails(self):
        self._login_as("cirugias_writer", self.writer_password)

        first = self.client.post(
            "/api/v1/surgeries", self._payload(), format="json", **self._csrf_headers(),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            "/api/v1/surgeries", self._payload(noExp="EXP-C002"), format="json",
            **self._csrf_headers(),
        )

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "SURGERY_TIME_CONFLICT")

    def test_overlapping_time_slot_fails(self):
        self._login_as("cirugias_writer", self.writer_password)

        first = self.client.post(
            "/api/v1/surgeries", self._payload(), format="json", **self._csrf_headers(),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            "/api/v1/surgeries",
            self._payload(noExp="EXP-C003", scheduledTime="09:30:00"),
            format="json",
            **self._csrf_headers(),
        )

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "SURGERY_TIME_CONFLICT")

    def test_cancel_requires_reason_and_cannot_repeat(self):
        self._login_as("cirugias_writer", self.writer_password)

        created = self.client.post(
            "/api/v1/surgeries", self._payload(), format="json", **self._csrf_headers(),
        )
        surgery_id = created.data["id"]

        from apps.catalogos.models import CatMotivoCancelacionCirugia
        reason = CatMotivoCancelacionCirugia.objects.create(name="Paciente no se presento")

        missing_reason = self.client.patch(
            f"/api/v1/surgeries/{surgery_id}/cancel", {}, format="json",
            **self._csrf_headers(),
        )
        self.assertEqual(missing_reason.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        cancel = self.client.patch(
            f"/api/v1/surgeries/{surgery_id}/cancel",
            {"reasonId": reason.id}, format="json",
            **self._csrf_headers(),
        )
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data["status"], SurgerySchedule.Status.CANCELADA)

        repeat = self.client.patch(
            f"/api/v1/surgeries/{surgery_id}/cancel",
            {"reasonId": reason.id}, format="json",
            **self._csrf_headers(),
        )
        self.assertEqual(repeat.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(repeat.data["code"], "SURGERY_ALREADY_CANCELLED")
