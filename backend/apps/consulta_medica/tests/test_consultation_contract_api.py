from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies, Permisos, Roles
from apps.consulta_medica.models import VisitConsultation
from apps.recepcion.models import Visit


class ConsultationContractsApiTests(APITestCase):
    def setUp(self):
        self.request_id = "33333333-3333-3333-3333-333333333333"
        self.doctor_password = "Doctor_123456"
        self.recepcion_password = "Recep_123456"

        self.doctor_user = self._create_user_with_role(
            username="doctor_user",
            email="doctor@example.com",
            password=self.doctor_password,
            role_code="DOCTOR",
            landing_route="/consultas",
        )
        self._create_user_with_role(
            username="recepcion_user",
            email="recepcion@example.com",
            password=self.recepcion_password,
            role_code="RECEPCION",
            landing_route="/recepcion",
        )
        self._create_user_with_role(
            username="clinico_user",
            email="clinico@example.com",
            password="Clinico_123456",
            role_code="CLINICO",
            landing_route="/clinico/consultas/doctor",
            permissions=["clinico:consultas:read"],
        )

        self.visit_ready = Visit.objects.create(
            folio="CNS-7001",
            no_exp="EXP7001",
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id="APP-7001",
            status="lista_para_doctor",
        )
        self.visit_in_consultation = Visit.objects.create(
            folio="CNS-7002",
            no_exp="EXP7002",
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id="APP-7002",
            status="en_consulta",
        )

        CatCies.objects.create(
            code="A090",
            description="GASTROENTERITIS",
            version="CIE-10",
            is_active=True,
        )
        CatCies.objects.create(
            code="J110",
            description="INFLUENZA",
            version="CIE-10",
            is_active=True,
        )
        CatCies.objects.create(
            code="1A33.0",
            description="CISTOISOSPORIASIS DEL INTESTINO DELGADO",
            version="CIE-10",
            is_active=True,
        )

    def _create_user_with_role(
        self,
        username,
        email,
        password,
        role_code,
        landing_route,
        permissions=None,
    ):
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
                "landing_route": landing_route,
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

    def test_start_consultation_happy_path_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_ready.id_visit}/consultation/start",
            {},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.visit_ready.id_visit)
        self.assertEqual(response.data["status"], "en_consulta")

        audit_event = AuditoriaEvento.objects.get(
            accion="ConsultationStarted",
            request_id=self.request_id,
        )
        self.assertEqual(audit_event.resultado, "SUCCESS")
        self.assertEqual(audit_event.meta.get("module"), "consulta_medica")

    def test_start_consultation_role_not_allowed(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_ready.id_visit}/consultation/start",
            {},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_start_consultation_allows_clinico_with_consultas_permission(self):
        self._login_as("clinico_user", "Clinico_123456")

        response = self.client.post(
            f"/api/v1/visits/{self.visit_ready.id_visit}/consultation/start",
            {},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "en_consulta")

    def test_close_consultation_happy_path_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/consultation/close",
            {
                "primaryDiagnosis": "Gastroenteritis aguda",
                "finalNote": "Reposo, hidratacion y seguimiento en 48h.",
                "cieCode": "A090",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("visit", response.data)
        self.assertIn("consultation", response.data)
        self.assertEqual(response.data["visit"]["status"], "cerrada")
        self.assertEqual(response.data["consultation"]["visitId"], self.visit_in_consultation.id_visit)

        consultation = VisitConsultation.objects.get(id_visit=self.visit_in_consultation)
        self.assertEqual(consultation.doctor_id, self.doctor_user.id_usuario)

        audit_event = AuditoriaEvento.objects.get(
            accion="ConsultationClosed",
            request_id=self.request_id,
        )
        self.assertEqual(audit_event.resultado, "SUCCESS")

    def test_save_diagnosis_happy_path_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/diagnosis",
            {
                "primaryDiagnosis": "Gastroenteritis aguda",
                "finalNote": "Paciente hidratado y estable.",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visitId"], self.visit_in_consultation.id_visit)
        self.assertEqual(response.data["status"], "en_consulta")
        self.assertEqual(response.data["primaryDiagnosis"], "Gastroenteritis aguda")
        self.assertEqual(response.data["finalNote"], "Paciente hidratado y estable.")

        consultation = VisitConsultation.objects.get(id_visit=self.visit_in_consultation)
        self.assertEqual(consultation.primary_diagnosis, "Gastroenteritis aguda")
        self.assertEqual(consultation.final_note, "Paciente hidratado y estable.")

        audit_event = AuditoriaEvento.objects.get(
            accion="DiagnosisSaved",
            request_id=self.request_id,
        )
        self.assertEqual(audit_event.resultado, "SUCCESS")

    def test_save_diagnosis_with_cie_code_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/diagnosis",
            {
                "primaryDiagnosis": "Gastroenteritis aguda",
                "finalNote": "Paciente hidratado y estable.",
                "cieCode": "a090",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cieCode"], "A090")

        consultation = VisitConsultation.objects.get(id_visit=self.visit_in_consultation)
        self.assertEqual(consultation.cie_id, "A090")

    def test_save_diagnosis_with_note_fields_contract(self):
        # his_notas ampliada (documento "Historia Clinica Unificada", 5.2).
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/diagnosis",
            {
                "primaryDiagnosis": "Gastroenteritis aguda",
                "finalNote": "Paciente hidratado y estable.",
                "currentIllness": "Evacuaciones liquidas de 2 dias.",
                "systemsReview": "",
                "diagnosticPlan": "Coprologico.",
                "therapeuticPlan": "Hidratacion oral.",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["currentIllness"], "Evacuaciones liquidas de 2 dias.")
        self.assertIsNone(response.data["systemsReview"])
        consultation = VisitConsultation.objects.get(id_visit=self.visit_in_consultation)
        self.assertEqual(consultation.diagnostic_plan, "Coprologico.")
        self.assertEqual(consultation.therapeutic_plan, "Hidratacion oral.")

    def test_search_cies_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.get(
            "/api/v1/visits/cies/search?search=gastro&limit=5",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["code"], "A090")
        self.assertEqual(response.data["items"][0]["description"], "GASTROENTERITIS")

    def test_search_cies_contract_matches_code_without_dot(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.get(
            "/api/v1/visits/cies/search?search=1A330&limit=5",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["code"], "1A33.0")

    def test_save_diagnosis_invalid_state_returns_visit_state_invalid(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_ready.id_visit}/diagnosis",
            {
                "primaryDiagnosis": "Dx",
                "finalNote": "Nota",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "VISIT_STATE_INVALID")
        self.assertEqual(response.data["status"], 409)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_save_prescriptions_happy_path_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/prescriptions",
            {
                "items": [
                    "Paracetamol 500mg cada 8h por 3 dias",
                    "Hidratacion oral libre",
                ]
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visitId"], self.visit_in_consultation.id_visit)
        self.assertEqual(response.data["status"], "en_consulta")
        self.assertEqual(
            response.data["items"],
            [
                "Paracetamol 500mg cada 8h por 3 dias",
                "Hidratacion oral libre",
            ],
        )

        audit_event = AuditoriaEvento.objects.get(
            accion="PrescriptionsSaved",
            request_id=self.request_id,
        )
        self.assertEqual(audit_event.resultado, "SUCCESS")

    def test_save_prescriptions_validation_error_when_items_are_empty(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/prescriptions",
            {
                "items": [],
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_close_consultation_supports_close_alias_route(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/close",
            {
                "primaryDiagnosis": "Dx alias",
                "finalNote": "Nota alias",
                "cieCode": "A090",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visit"]["status"], "cerrada")

    def test_close_consultation_idempotent_retry_returns_same_contract(self):
        self._login_as("doctor_user", self.doctor_password)

        payload = {
            "primaryDiagnosis": "Dx de egreso",
            "finalNote": "Nota final idempotente",
            "cieCode": "A090",
        }

        first_response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/consultation/close",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/consultation/close",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data["visit"]["status"], "cerrada")
        self.assertEqual(
            second_response.data["consultation"]["primaryDiagnosis"],
            payload["primaryDiagnosis"],
        )

    def test_close_consultation_allows_clinico_with_consultas_permission(self):
        self._login_as("clinico_user", "Clinico_123456")

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/consultation/close",
            {
                "primaryDiagnosis": "Infeccion de vias respiratorias",
                "finalNote": "Alta con recomendaciones generales.",
                "cieCode": "A090",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["visit"]["status"], "cerrada")

    def test_close_consultation_invalid_payload_returns_validation_error(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_in_consultation.id_visit}/consultation/close",
            {"primaryDiagnosis": "", "finalNote": ""},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)
        self.assertIn("details", response.data)

    def test_close_consultation_invalid_state_returns_visit_state_invalid(self):
        self._login_as("doctor_user", self.doctor_password)

        response = self.client.post(
            f"/api/v1/visits/{self.visit_ready.id_visit}/consultation/close",
            {
                "primaryDiagnosis": "Dx",
                "finalNote": "Nota",
                "cieCode": "A090",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "VISIT_STATE_INVALID")
        self.assertEqual(response.data["status"], 409)
        self.assertEqual(response.data["requestId"], self.request_id)
