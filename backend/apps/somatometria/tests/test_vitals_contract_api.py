from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import (
    AuditoriaEvento,
    RelRolPermiso,
    RelUsuarioOverride,
    RelUsuarioRol,
)
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.recepcion.models import Visit
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


class VitalsContractsApiTests(APITestCase):
    def setUp(self):
        self.request_id = "22222222-2222-2222-2222-222222222222"
        self.somato_password = "Somato_123456"
        self.recepcion_password = "Recep_123456"

        self._create_user_with_role(
            username="somato_user",
            email="somato@example.com",
            password=self.somato_password,
            role_code="SOMATOMETRIA",
            permissions=["clinico:somatometria:read"],
        )
        self._create_user_with_role(
            username="somato_role_only_user",
            email="somato_role_only@example.com",
            password="SomatoRoleOnly_123456",
            role_code="SOMATOMETRIA",
            permissions=["clinico:somatometria:read"],
        )
        role_only_user = SyUsuario.objects.get(usuario="somato_role_only_user")
        denied_permission = Permisos.objects.get(codigo="clinico:somatometria:read")
        RelUsuarioOverride.objects.create(
            id_usuario=role_only_user,
            id_permiso=denied_permission,
            efecto="DENY",
        )
        self._create_user_with_role(
            username="recepcion_user",
            email="recepcion2@example.com",
            password=self.recepcion_password,
            role_code="RECEPCION",
        )
        self._create_user_with_role(
            username="clinico_user",
            email="clinico2@example.com",
            password="Clinico_123456",
            role_code="CLINICO",
            permissions=["clinico:somatometria:read"],
        )

        self.visit_in_somato = Visit.objects.create(
            folio="SMT-9001",
            patient=_paciente_de_llave("EXP9001", 0),
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id="APP-SMT-9001",
            status="en_somatometria",
        )
        self.visit_in_wait = Visit.objects.create(
            folio="SMT-9002",
            patient=_paciente_de_llave("EXP9002", 0),
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_espera",
        )

    def _create_user_with_role(self, username, email, password, role_code, permissions=None):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=email,
            clave_hash=make_password(password),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user,
            nombre=username,
            paterno="Test",
            materno="User",
        )
        role, _ = Roles.objects.get_or_create(
            rol=role_code,
            defaults={
                "desc_rol": f"Rol {role_code}",
                "landing_route": "/clinico/somatometria",
            },
        )
        RelUsuarioRol.objects.create(
            id_usuario=user,
            id_rol=role,
            is_primary=True,
        )

        for permission_code in permissions or []:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code,
                defaults={
                    "descripcion": permission_code,
                    "is_active": True,
                },
            )
            RelRolPermiso.objects.get_or_create(
                id_rol=role,
                id_permiso=permission,
            )

        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        # Redis (sesion unica) no se limpia entre tests como la DB -- un
        # user_id reciclado puede arrastrar una sesion "activa" de una
        # corrida anterior y el login choca con SESSION_ALREADY_ACTIVE (409).
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

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _valid_payload(self):
        return {
            "weightKg": 70,
            "heightCm": 175,
            "temperatureC": 36.6,
            "oxygenSaturationPct": 98,
        }

    def test_capture_vitals_happy_path_contract(self):
        self._login_as("somato_user", self.somato_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visitId"], self.visit_in_somato.id_visit)
        self.assertEqual(response.data["status"], "lista_para_doctor")
        self.assertIn("vitals", response.data)
        self.assertIn("waistCircumferenceCm", response.data["vitals"])
        self.assertIsNone(response.data["vitals"]["waistCircumferenceCm"])
        self.assertAlmostEqual(response.data["vitals"]["bmi"], 22.86, places=2)

        self.visit_in_somato.refresh_from_db()
        self.assertEqual(self.visit_in_somato.status, "lista_para_doctor")

        audit_event = AuditoriaEvento.objects.get(
            accion="VitalsCompleted",
            request_id=self.request_id,
        )
        self.assertEqual(audit_event.resultado, "SUCCESS")
        self.assertEqual(audit_event.meta.get("module"), "somatometria")
        self.assertEqual(audit_event.meta.get("visitId"), self.visit_in_somato.id_visit)

    def test_capture_vitals_missing_csrf_returns_permission_denied(self):
        self._login_as("somato_user", self.somato_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_capture_vitals_allows_clinico_with_somatometria_permission(self):
        self._login_as("clinico_user", "Clinico_123456")

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "lista_para_doctor")

    def test_capture_vitals_missing_required_field_returns_validation_error(self):
        self._login_as("somato_user", self.somato_password)

        payload = self._valid_payload()
        payload.pop("weightKg")
        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)
        self.assertIn("details", response.data)
        self.assertIn("weightKg", response.data["details"])

    def test_capture_vitals_out_of_range_returns_validation_error(self):
        self._login_as("somato_user", self.somato_password)

        payload = self._valid_payload()
        payload["temperatureC"] = 50
        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)
        self.assertIn("details", response.data)
        self.assertIn("temperatureC", response.data["details"])

    def test_capture_vitals_invalid_waist_circumference_returns_validation_error(self):
        self._login_as("somato_user", self.somato_password)

        payload = self._valid_payload()
        payload["waistCircumferenceCm"] = 10
        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)
        self.assertIn("details", response.data)
        self.assertIn("waistCircumferenceCm", response.data["details"])

    def test_capture_vitals_incomplete_minimum_data_returns_vitals_incomplete(self):
        self._login_as("somato_user", self.somato_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            {
                "weightKg": 70,
                "heightCm": 175,
                "oxygenSaturationPct": 98,
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VITALS_INCOMPLETE")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)

        self.visit_in_somato.refresh_from_db()
        self.assertEqual(self.visit_in_somato.status, "en_somatometria")

    def test_capture_vitals_invalid_state_returns_visit_state_invalid(self):
        self._login_as("somato_user", self.somato_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_wait.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "VISIT_STATE_INVALID")
        self.assertEqual(response.data["status"], 409)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_capture_vitals_role_not_allowed(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_capture_vitals_role_only_user_without_capability_is_denied(self):
        self._login_as("somato_role_only_user", "SomatoRoleOnly_123456")

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_capture_vitals_visit_not_found(self):
        self._login_as("somato_user", self.somato_password)

        response = self.client.post(
            "/api/v1/visits/999999/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "VISIT_NOT_FOUND")
        self.assertEqual(response.data["status"], 404)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_capture_vitals_accepts_optional_fields(self):
        self._login_as("somato_user", self.somato_password)

        payload = self._valid_payload()
        payload.update(
            {
                "heartRateBpm": 80,
                "respiratoryRateBpm": 16,
                "bloodPressureSystolic": 118,
                "bloodPressureDiastolic": 76,
                "waistCircumferenceCm": 95,
                "notes": "Paciente cooperador durante la toma.",
            }
        )

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "lista_para_doctor")
        self.assertEqual(response.data["vitals"]["heartRateBpm"], 80)
        self.assertEqual(response.data["vitals"]["respiratoryRateBpm"], 16)
        self.assertEqual(response.data["vitals"]["bloodPressureSystolic"], 118)
        self.assertEqual(response.data["vitals"]["bloodPressureDiastolic"], 76)
        self.assertEqual(response.data["vitals"]["waistCircumferenceCm"], 95)

    def test_capture_vitals_without_csrf_returns_permission_denied(self):
        self._login_as("somato_user", self.somato_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_somato.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)
