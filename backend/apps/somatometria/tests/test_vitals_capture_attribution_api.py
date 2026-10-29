"""
Test de integracion (APIClient) de la atribucion de autoria y el rechazo
de doble captura (Fase 2, tasks 2.7 y 2.8 del change
somatometria-modulo-integral).

- "Captura inicial registra solo `captured_by`" (spec
  `somatometria/ficha-vitals`).
- "Segundo POST sobre visita ya capturada" (spec
  `somatometria/edicion-auditada`): 409 VITALS_ALREADY_CAPTURED, fila
  intacta.
"""
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.recepcion.models import Visit
from apps.somatometria.models import VisitVitalSigns
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


class VitalsCaptureAttributionApiTests(APITestCase):
    def setUp(self):
        self.request_id = "44444444-4444-4444-4444-444444444444"
        self.somato_password = "Somato_123456"

        self.user = self._create_user_with_role(
            username="somato_attr_user",
            email="somato_attr@example.com",
            password=self.somato_password,
            role_code="SOMATOMETRIA",
            permissions=["clinico:somatometria:read"],
        )

        self.visit = Visit.objects.create(
            folio="ATTR-0001",
            patient=_paciente_de_llave("EXP-ATTR-API-1", 0),
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_somatometria",
            service_type=Visit.ServiceType.MEDICINA_GENERAL,
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

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _valid_payload(self, **overrides):
        payload = {
            "weightKg": 70,
            "heightCm": 175,
            "temperatureC": 36.6,
            "oxygenSaturationPct": 98,
        }
        payload.update(overrides)
        return payload

    def test_initial_capture_records_only_captured_by(self):
        self._login_as("somato_attr_user", self.somato_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertEqual(row.captured_by_id, self.user.id_usuario)
        self.assertIsNone(row.updated_by_id)

        # El contrato tambien expone la atribucion (D4).
        self.assertEqual(response.data["vitals"]["capturedBy"]["id"], self.user.id_usuario)
        self.assertIsNone(response.data["vitals"]["updatedBy"])

    def test_second_capture_on_same_visit_returns_409_and_row_untouched(self):
        self._login_as("somato_attr_user", self.somato_password)

        first_response = self.client.post(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_payload(weightKg=90, heightCm=160),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second_response.data["code"], "VITALS_ALREADY_CAPTURED")

        # La fila NO se sobreescribio con el segundo intento.
        self.assertEqual(VisitVitalSigns.objects.filter(id_visit=self.visit).count(), 1)
        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertEqual(float(row.weight_kg), 70.0)
        self.assertEqual(float(row.height_cm), 175.0)
        self.assertEqual(row.captured_by_id, self.user.id_usuario)
