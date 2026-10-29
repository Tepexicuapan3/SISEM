"""
Test de integracion (APIClient) del reuso mismo dia (Fase 2, task 2.10 del
change somatometria-reuso-signos-mismo-dia). Valida spec "Enfermera reusa
la captura de hoy": el POST con `reusedFromVisitId` crea una fila NUEVA en
`VisitVitalSigns` con la FK de auditoria poblada -- nunca fusiona ni omite
filas -- y sigue transicionando el estado de la visita como cualquier
captura. Tambien confirma que el GET expone `todayCapture` antes de que la
enfermera decida.
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
from apps.somatometria.repositories.vitals_repository import VitalsRepository
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


class VitalsReuseApiTests(APITestCase):
    def setUp(self):
        self.request_id = "33333333-3333-3333-3333-333333333333"
        self.somato_password = "Somato_123456"

        self._create_user_with_role(
            username="somato_reuse_user",
            email="somato_reuse@example.com",
            password=self.somato_password,
            role_code="SOMATOMETRIA",
            permissions=["clinico:somatometria:read"],
        )

        self.source_visit = Visit.objects.create(
            folio="REUSE-SOURCE-1",
            patient=_paciente_de_llave("EXP-REUSE-1", 0),
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="lista_para_doctor",
            service_type=Visit.ServiceType.MEDICINA_GENERAL,
        )
        VitalsRepository.create_for_visit(
            self.source_visit,
            {
                "weightKg": 70,
                "heightCm": 175,
                "temperatureC": 36.5,
                "oxygenSaturationPct": 97,
                "bmi": 22.86,
            },
            captured_by=None,
        )

        self.current_visit = Visit.objects.create(
            folio="REUSE-CURRENT-1",
            patient=_paciente_de_llave("EXP-REUSE-1", 0),
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_somatometria",
            service_type=Visit.ServiceType.ESPECIALIDAD,
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

    def test_get_vitals_exposes_today_capture_before_reuse_decision(self):
        self._login_as("somato_reuse_user", self.somato_password)

        response = self.client.get(
            f"/api/v1/visits/{self.current_visit.id_visit}/vitals",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("todayCapture", response.data)
        today_capture = response.data["todayCapture"]
        self.assertIsNotNone(today_capture)
        self.assertEqual(today_capture["sourceVisitId"], self.source_visit.id_visit)
        self.assertEqual(today_capture["sourceFolio"], self.source_visit.folio)
        self.assertEqual(
            today_capture["sourceServiceType"], Visit.ServiceType.MEDICINA_GENERAL
        )
        self.assertEqual(today_capture["values"]["weightKg"], 70.0)
        # "values" es solo metricas -- no lleva capturedAt/reusedFromVisitId
        # anidados (esos ya viajan en el nivel de "todayCapture").
        self.assertNotIn("capturedAt", today_capture["values"])

    def test_reuse_creates_new_row_with_source_fk_and_transitions_status(self):
        self._login_as("somato_reuse_user", self.somato_password)

        payload = {
            "weightKg": 71,
            "heightCm": 175,
            "temperatureC": 36.7,
            "oxygenSaturationPct": 98,
            "reusedFromVisitId": self.source_visit.id_visit,
        }

        response = self.client.post(
            f"/api/v1/visits/{self.current_visit.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "lista_para_doctor")
        self.assertEqual(
            response.data["vitals"]["reusedFromVisitId"], self.source_visit.id_visit
        )
        # D5 -- el servidor NUNCA copia los valores del origen: los
        # guardados son siempre los del payload de esta captura.
        self.assertEqual(response.data["vitals"]["weightKg"], 71.0)
        self.assertEqual(response.data["vitals"]["temperatureC"], 36.7)

        # Gap cerrado por Fase 3.9: el medico ya no solo ve que hubo reuso,
        # tambien ve folio/especialidad/hora de la visita ORIGEN -- mismos
        # nombres de campo que `todayCapture` (`sourceFolio`,
        # `sourceServiceType`, `capturedAt`) para consistencia del contrato.
        reused_from = response.data["vitals"]["reusedFrom"]
        self.assertIsNotNone(reused_from)
        self.assertEqual(reused_from["sourceVisitId"], self.source_visit.id_visit)
        self.assertEqual(reused_from["sourceFolio"], self.source_visit.folio)
        self.assertEqual(
            reused_from["sourceServiceType"], Visit.ServiceType.MEDICINA_GENERAL
        )
        self.assertIsNotNone(reused_from["capturedAt"])

        # El origen (visita fuente) nunca tuvo reuso -- retrocompatibilidad:
        # `reusedFromVisitId` y `reusedFrom` siguen None cuando no aplica.
        source_row = VisitVitalSigns.objects.get(id_visit=self.source_visit)
        source_contract = VitalsRepository.to_contract(source_row)
        self.assertIsNone(source_contract["reusedFromVisitId"])
        self.assertIsNone(source_contract["reusedFrom"])

        # NOM-024: sigue existiendo UNA fila por visita -- nada se fusiona
        # ni se omite por reusar.
        self.assertEqual(VisitVitalSigns.objects.count(), 2)

        current_row = VisitVitalSigns.objects.get(id_visit=self.current_visit)
        self.assertEqual(current_row.reused_from_visit_id, self.source_visit.id_visit)
        self.assertEqual(float(current_row.weight_kg), 71.0)

        source_row = VisitVitalSigns.objects.get(id_visit=self.source_visit)
        self.assertIsNone(source_row.reused_from_visit_id)
        self.assertEqual(float(source_row.weight_kg), 70.0)

        self.current_visit.refresh_from_db()
        self.assertEqual(self.current_visit.status, "lista_para_doctor")

    def test_reuse_with_invalid_source_returns_422_with_reuse_code(self):
        self._login_as("somato_reuse_user", self.somato_password)

        payload = {
            "weightKg": 71,
            "heightCm": 175,
            "temperatureC": 36.7,
            "oxygenSaturationPct": 98,
            "reusedFromVisitId": self.current_visit.id_visit,
        }

        response = self.client.post(
            f"/api/v1/visits/{self.current_visit.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "REUSE_SAME_VISIT")

        # Un 422 de validacion del reuso no debe dejar efectos secundarios:
        # ni fila nueva, ni cambio de estado.
        self.assertFalse(VisitVitalSigns.objects.filter(id_visit=self.current_visit).exists())
        self.current_visit.refresh_from_db()
        self.assertEqual(self.current_visit.status, "en_somatometria")
