from datetime import datetime, timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import MotivoCita, Permisos, Roles, TipoDeCitas
from apps.somatometria.repositories.vitals_repository import VitalsRepository


class VisitContractsApiTests(APITestCase):
    def setUp(self):
        self.request_id = "11111111-1111-1111-1111-111111111111"
        self.recepcion_password = "Recep_123456"
        self.medico_password = "Medico_123456"
        self.admin_password = "Admin_123456"
        # Motivo tipificado (catálogo cargado por la migración de datos
        # catalogos/0021_motivos_cita) -- reemplaza el texto libre que
        # antes viajaba en "motivo".
        self.motivo_cancelacion_id = MotivoCita.objects.get(
            name="Cancelada por el paciente"
        ).id

        self._create_user_with_role(
            username="recepcion_user",
            email="recepcion@example.com",
            password=self.recepcion_password,
            role_code="RECEPCION",
            permissions=[
                "recepcion:fichas:medicina_general:read",
                "recepcion:fichas:medicina_general:create",
            ],
        )
        self._create_user_with_role(
            username="medico_user",
            email="medico@example.com",
            password=self.medico_password,
            role_code="MEDICO",
        )
        # doctorId ahora es FK real a SyUsuario (ver migracion
        # 0019_doctor_fk_integrity) -- ya no acepta cualquier entero suelto.
        self.medico_user_id = SyUsuario.objects.get(usuario="medico_user").id_usuario
        self._create_user_with_role(
            username="clinico_user",
            email="clinico@example.com",
            password="Clinico_123456",
            role_code="CLINICO",
            permissions=["clinico:somatometria:read"],
        )
        self._create_user_with_role(
            username="admin_user",
            email="admin@example.com",
            password=self.admin_password,
            role_code="ADMIN",
            landing_route="/admin",
            is_admin=True,
        )

    def _create_user_with_role(
        self,
        username,
        email,
        password,
        role_code,
        permissions=None,
        landing_route=None,
        is_admin=False,
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
        resolved_landing_route = landing_route or (
            "/recepcion" if role_code == "RECEPCION" else "/consultas"
        )
        role = Roles.objects.create(
            rol=role_code,
            desc_rol=f"Rol {role_code}",
            landing_route=resolved_landing_route,
            is_admin=is_admin,
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

    def _create_visit(self, patient_id=1001, arrival_type="appointment", **kwargs):
        # patient_id es solo un identificador arbitrario para distinguir
        # visitas en el test -- la API real pide noExp/pkNum (ver
        # CreateVisitSerializer), no patientId (campo eliminado del modelo
        # Visit hace tiempo, migracion 0008_remove_visit_patient_id).
        payload = {
            "noExp": f"EXP{patient_id}",
            "pkNum": 0,
            "arrivalType": arrival_type,
            "serviceType": kwargs.get("serviceType", "medicina_general"),
        }

        appointment_id = kwargs.get("appointmentId")
        if appointment_id is None and arrival_type == "appointment":
            appointment_id = "APP-123"
        if appointment_id is not None:
            payload["appointmentId"] = appointment_id

        if "doctorId" in kwargs and kwargs.get("doctorId") is not None:
            payload["doctorId"] = kwargs["doctorId"]
        if "notes" in kwargs and kwargs.get("notes") is not None:
            payload["notes"] = kwargs["notes"]
        response = self.client.post(
            "/api/v1/visits",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def test_create_visit_happy_path_contract(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP1234",
                "pkNum": 0,
                "arrivalType": "appointment",
                "serviceType": "especialidad",
                "appointmentId": "APP-456",
                "doctorId": self.medico_user_id,
                "notes": "Paciente puntual",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("folio", response.data)
        self.assertEqual(response.data["noExp"], "EXP1234")
        self.assertEqual(response.data["pkNum"], 0)
        self.assertEqual(response.data["arrivalType"], "appointment")
        self.assertEqual(response.data["serviceType"], "especialidad")
        self.assertEqual(response.data["appointmentId"], "APP-456")
        self.assertEqual(response.data["doctorId"], self.medico_user_id)
        self.assertEqual(response.data["notes"], "Paciente puntual")
        self.assertEqual(response.data["status"], "en_espera")

    def test_create_visit_invalid_payload_returns_validation_error(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {"arrivalType": "appointment", "appointmentId": "APP-001"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)
        self.assertIn("details", response.data)
        # Plan contraer la llave vieja: el paciente se indica con idPaciente.
        self.assertIn("idPaciente", response.data["details"])

    def test_create_visit_role_not_allowed(self):
        self._login_as("medico_user", self.medico_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP1234",
                "arrivalType": "appointment",
                "appointmentId": "APP-789",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_create_visit_allows_admin_with_wildcard_permissions(self):
        self._login_as("admin_user", self.admin_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP1235",
                "arrivalType": "appointment",
                "appointmentId": "APP-ADMIN-001",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["noExp"], "EXP1235")
        self.assertEqual(response.data["status"], "en_espera")

    def test_list_visits_happy_path_contract(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit_without_vitals = self._create_visit(patient_id=2001)
        visit_with_vitals = self._create_visit(
            patient_id=2002,
            arrival_type="walk_in",
            serviceType="urgencias",
        )
        # Use VitalsRepository from somatometria domain instead of direct model import
        from apps.recepcion.models import Visit

        visit = Visit.objects.get(id_visit=visit_with_vitals["id"])
        VitalsRepository.create_for_visit(
            visit,
            {
                "weightKg": 70,
                "heightCm": 175,
                "temperatureC": 36.6,
                "oxygenSaturationPct": 98,
                "bmi": 22.86,
            },
            captured_by=None,
        )

        response = self.client.get(
            "/api/v1/visits?page=1&pageSize=20",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("page", response.data)
        self.assertIn("pageSize", response.data)
        self.assertIn("total", response.data)
        self.assertIn("totalPages", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 2)

        first_item = response.data["items"][0]
        self.assertIn("id", first_item)
        self.assertIn("folio", first_item)
        self.assertIn("noExp", first_item)
        self.assertIn("arrivalType", first_item)
        self.assertIn("serviceType", first_item)
        self.assertIn("appointmentId", first_item)
        self.assertIn("doctorId", first_item)
        self.assertIn("notes", first_item)
        self.assertIn("status", first_item)
        self.assertIn("vitals", first_item)

        items_by_patient = {item["noExp"]: item for item in response.data["items"]}
        self.assertIsNone(items_by_patient[visit_without_vitals["noExp"]]["vitals"])

        # Narrowing de recepcion (D3, somatometria-modulo-integral):
        # `recepcion_user` solo tiene `recepcion:fichas:*:create`, sin
        # `flow.somatometria.queue.read` ni `flow.doctor.queue.read` --> el
        # LIST NO expone valores numericos, solo estado.
        vitals_contract = items_by_patient[visit_with_vitals["noExp"]]["vitals"]
        self.assertNotIn("weightKg", vitals_contract)
        self.assertNotIn("heightCm", vitals_contract)
        self.assertNotIn("bmi", vitals_contract)
        self.assertNotIn("bloodPressureSystolic", vitals_contract)
        self.assertNotIn("glucosaCapilarMgdl", vitals_contract)
        self.assertTrue(vitals_contract["hasVitals"])
        self.assertIsNotNone(vitals_contract["capturedAt"])
        # Retrocompatibilidad: sin reuso, `reusedFromVisitId` y el nuevo
        # `reusedFrom` (folio/servicio/hora de origen) son ambos None.
        self.assertIsNone(vitals_contract["reusedFromVisitId"])
        self.assertIsNone(vitals_contract["reusedFrom"])

    def test_list_visits_shows_full_vitals_values_for_somatometria_reader(self):
        """
        Contraparte de `test_list_visits_happy_path_contract` (D3): un
        caller CON `flow.somatometria.queue.read` (derivado de
        `clinico:somatometria:read`) sigue viendo el contrato COMPLETO de
        vitals en el LIST -- el narrowing es exclusivo de recepcion.
        """
        self._login_as("recepcion_user", self.recepcion_password)
        visit_with_vitals = self._create_visit(
            patient_id=2004,
            arrival_type="walk_in",
            serviceType="urgencias",
        )
        from apps.recepcion.models import Visit

        visit = Visit.objects.get(id_visit=visit_with_vitals["id"])
        VitalsRepository.create_for_visit(
            visit,
            {
                "weightKg": 70,
                "heightCm": 175,
                "temperatureC": 36.6,
                "oxygenSaturationPct": 98,
                "bmi": 22.86,
            },
            captured_by=None,
        )

        self._login_as("clinico_user", "Clinico_123456")
        response = self.client.get(
            "/api/v1/visits?page=1&pageSize=20",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items_by_patient = {item["noExp"]: item for item in response.data["items"]}
        vitals_contract = items_by_patient[visit_with_vitals["noExp"]]["vitals"]
        self.assertEqual(vitals_contract["weightKg"], 70.0)
        self.assertEqual(vitals_contract["heightCm"], 175.0)
        self.assertTrue(vitals_contract["hasVitals"])

    def test_list_visits_filters_by_service_type(self):
        self._login_as("recepcion_user", self.recepcion_password)
        self._create_visit(patient_id=2401, serviceType="medicina_general")
        self._create_visit(
            patient_id=2402,
            arrival_type="walk_in",
            serviceType="urgencias",
        )

        response = self.client.get(
            "/api/v1/visits?page=1&pageSize=20&serviceType=urgencias",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)
        for item in response.data["items"]:
            self.assertEqual(item["serviceType"], "urgencias")

    def test_create_visit_urgencias_requires_walk_in(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP2233",
                "arrivalType": "appointment",
                "serviceType": "urgencias",
                "appointmentId": "APP-URG-01",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("details", response.data)
        self.assertIn("arrivalType", response.data["details"])

    def test_list_visits_allows_clinico_with_somatometria_permission(self):
        self._login_as("recepcion_user", self.recepcion_password)
        self._create_visit(patient_id=2301)

        self._login_as("clinico_user", "Clinico_123456")
        response = self.client.get(
            "/api/v1/visits?page=1&pageSize=20&status=en_espera",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)

    def test_list_visits_filters_by_status_and_doctor(self):
        self._login_as("recepcion_user", self.recepcion_password)
        other_doctor_id = SyUsuario.objects.get(usuario="admin_user").id_usuario
        self._create_visit(patient_id=2101, doctorId=self.medico_user_id)
        self._create_visit(patient_id=2102, doctorId=other_doctor_id)

        response = self.client.get(
            f"/api/v1/visits?page=1&pageSize=20&status=en_espera&doctorId={self.medico_user_id}",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)
        for item in response.data["items"]:
            self.assertEqual(item["status"], "en_espera")
            self.assertEqual(item["doctorId"], self.medico_user_id)

    def test_list_visits_filters_by_date(self):
        self._login_as("recepcion_user", self.recepcion_password)
        self._create_visit(patient_id=2201)
        today = timezone.localdate().isoformat()

        response = self.client.get(
            f"/api/v1/visits?page=1&pageSize=20&date={today}",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)

    def test_list_visits_filters_by_fecha_desde_and_fecha_hasta(self):
        # Regresion: VisitListView.get() validaba fechaDesde/fechaHasta (y
        # folio) via ListVisitsQuerySerializer pero nunca los pasaba a
        # list_visits(), por lo que el filtro de rango de fecha era un no-op
        # silencioso -- el backend aceptaba el parametro, lo validaba, y lo
        # ignoraba al armar la query.
        self._login_as("recepcion_user", self.recepcion_password)
        visit_old = self._create_visit(patient_id=2601)
        visit_recent = self._create_visit(patient_id=2602)

        from apps.recepcion.models import Visit

        old_date = timezone.localdate() - timedelta(days=10)
        Visit.objects.filter(id_visit=visit_old["id"]).update(
            fch_alta=timezone.make_aware(datetime.combine(old_date, datetime.min.time()))
        )

        today = timezone.localdate().isoformat()
        response = self.client.get(
            f"/api/v1/visits?page=1&pageSize=20&fechaDesde={today}&fechaHasta={today}",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_no_exp = {item["noExp"] for item in response.data["items"]}
        self.assertIn(visit_recent["noExp"], returned_no_exp)
        self.assertNotIn(visit_old["noExp"], returned_no_exp)

    def test_list_visits_filters_by_folio(self):
        # Mismo bug que arriba tambien afectaba a `folio` -- confirmamos que
        # ahora se pasa correctamente al use case.
        self._login_as("recepcion_user", self.recepcion_password)
        visit_a = self._create_visit(patient_id=2701)
        self._create_visit(patient_id=2702)

        response = self.client.get(
            f"/api/v1/visits?page=1&pageSize=20&folio={visit_a['folio']}",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)
        for item in response.data["items"]:
            self.assertEqual(item["folio"], visit_a["folio"])

    def test_list_visits_role_not_allowed(self):
        self._login_as("medico_user", self.medico_password)

        response = self.client.get(
            "/api/v1/visits",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_patch_visit_status_cancelada_happy_path(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3001)

        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {
                "targetStatus": "cancelada",
                "motivoCancelacionId": self.motivo_cancelacion_id,
                "motivoDetalle": "El paciente solicito reagendar.",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], visit["id"])
        self.assertEqual(response.data["status"], "cancelada")

        from apps.recepcion.models import Visit
        visit_obj = Visit.objects.get(id_visit=visit["id"])
        self.assertEqual(visit_obj.motivo_cancelacion_id, self.motivo_cancelacion_id)
        self.assertEqual(visit_obj.motivo_detalle, "El paciente solicito reagendar.")

    def test_patch_visit_status_cancelada_without_motivo_returns_422(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3008)

        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "cancelada"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VISIT_MOTIVO_REQUERIDO")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)

        from apps.recepcion.models import Visit
        visit_obj = Visit.objects.get(id_visit=visit["id"])
        self.assertEqual(visit_obj.status, "en_espera")
        self.assertIsNone(visit_obj.motivo_cancelacion_id)

    def test_patch_visit_status_no_show_happy_path(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3002)

        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "no_show"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], visit["id"])
        self.assertEqual(response.data["status"], "no_show")

    def test_patch_visit_status_en_somatometria_happy_path(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3006)

        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "en_somatometria"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], visit["id"])
        self.assertEqual(response.data["status"], "en_somatometria")

    def test_visit_en_espera_has_null_en_somatometria_at(self):
        """Una visita que nunca paso por somatometria no tiene ese timestamp."""
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3101)

        response = self.client.get(
            "/api/v1/visits?page=1&pageSize=20",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items_by_id = {item["id"]: item for item in response.data["items"]}
        self.assertIn("enSomatometriaAt", items_by_id[visit["id"]])
        self.assertIsNone(items_by_id[visit["id"]]["enSomatometriaAt"])

    def test_visit_transitioned_to_en_somatometria_exposes_timestamp(self):
        """El PATCH que transiciona a en_somatometria devuelve el changed_at del log NOM-024."""
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3102)

        patch_response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "en_somatometria"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(patch_response.data["enSomatometriaAt"])

        from apps.recepcion.models import VisitStatusLog
        log_entry = VisitStatusLog.objects.get(
            visit_id=visit["id"], to_status="en_somatometria"
        )
        self.assertEqual(
            patch_response.data["enSomatometriaAt"],
            log_entry.changed_at.isoformat(),
        )

        # Tambien debe reflejarse via GET (list_paginated), no solo en la
        # respuesta directa del PATCH.
        list_response = self.client.get(
            "/api/v1/visits?page=1&pageSize=20",
            HTTP_X_REQUEST_ID=self.request_id,
        )
        items_by_id = {item["id"]: item for item in list_response.data["items"]}
        self.assertEqual(
            items_by_id[visit["id"]]["enSomatometriaAt"],
            log_entry.changed_at.isoformat(),
        )

    def test_en_somatometria_at_persists_when_visit_advances_further(self):
        """El timestamp de somatometria no se pierde al avanzar de estado."""
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3103, doctorId=self.medico_user_id)

        self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "en_somatometria"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        from apps.recepcion.models import Visit, VisitStatusLog
        log_entry = VisitStatusLog.objects.get(
            visit_id=visit["id"], to_status="en_somatometria"
        )

        # Avanza el estado directamente en el modelo (simula el flujo real
        # de somatometria -> lista_para_doctor -> en_consulta -> cerrada,
        # sin depender de los endpoints de otro dominio).
        visit_obj = Visit.objects.get(id_visit=visit["id"])
        for next_status in ("lista_para_doctor", "en_consulta", "cerrada"):
            visit_obj.status = next_status
            visit_obj.save(update_fields=["status", "fch_modf"])

            response = self.client.get(
                "/api/v1/visits?page=1&pageSize=20",
                HTTP_X_REQUEST_ID=self.request_id,
            )
            items_by_id = {item["id"]: item for item in response.data["items"]}
            self.assertEqual(
                items_by_id[visit["id"]]["enSomatometriaAt"],
                log_entry.changed_at.isoformat(),
                f"se perdio el timestamp al avanzar a {next_status}",
            )

    def test_patch_visit_status_invalid_payload_returns_validation_error(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3003)

        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "en_consulta"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["status"], 422)
        self.assertEqual(response.data["requestId"], self.request_id)
        self.assertIn("details", response.data)
        self.assertIn("targetStatus", response.data["details"])

    def test_patch_visit_status_role_not_allowed(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3004)

        self._login_as("medico_user", self.medico_password)
        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "cancelada"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
        self.assertEqual(response.data["status"], 403)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_patch_visit_status_allows_admin_with_wildcard_permissions(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3007)

        self._login_as("admin_user", self.admin_password)
        response = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {
                "targetStatus": "cancelada",
                "motivoCancelacionId": self.motivo_cancelacion_id,
                "motivoDetalle": "Cancelacion administrativa.",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], visit["id"])
        self.assertEqual(response.data["status"], "cancelada")

    def test_patch_visit_status_invalid_transition_returns_visit_state_invalid(self):
        self._login_as("recepcion_user", self.recepcion_password)
        visit = self._create_visit(patient_id=3005)

        first_patch = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {
                "targetStatus": "cancelada",
                "motivoCancelacionId": self.motivo_cancelacion_id,
                "motivoDetalle": "El paciente ya no puede asistir.",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(first_patch.status_code, status.HTTP_200_OK)

        second_patch = self.client.patch(
            f"/api/v1/visits/{visit['id']}/status",
            {"targetStatus": "no_show"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(second_patch.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second_patch.data["code"], "VISIT_STATE_INVALID")
        self.assertEqual(second_patch.data["status"], 409)
        self.assertEqual(second_patch.data["requestId"], self.request_id)

    def test_patch_visit_status_visit_not_found(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.patch(
            "/api/v1/visits/999999/status",
            {"targetStatus": "cancelada"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "VISIT_NOT_FOUND")
        self.assertEqual(response.data["status"], 404)
        self.assertEqual(response.data["requestId"], self.request_id)

    def test_post_visit_missing_csrf_header_returns_permission_denied(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP4444",
                "arrivalType": "appointment",
                "appointmentId": "APP-CSRF",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_create_visit_double_submit_returns_duplicate_error(self):
        self._login_as("recepcion_user", self.recepcion_password)

        first = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP5555",
                "arrivalType": "appointment",
                "appointmentId": "APP-DUP-1",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP5555",
                "arrivalType": "appointment",
                "appointmentId": "APP-DUP-2",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "VISIT_DUPLICATE_SUBMIT")
        self.assertEqual(second.data["requestId"], self.request_id)

    def test_create_visit_with_invalid_tipo_cita_id_returns_validation_error(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP6001",
                "arrivalType": "walk_in",
                "tipoCitaId": 999999,
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("details", response.data)
        self.assertIn("tipoCitaId", response.data["details"])

    def test_create_visit_with_soft_deleted_tipo_cita_id_persists_and_exposes_name(self):
        # Decision 2 del design: se valida EXISTENCIA, nunca `is_active` --
        # un tipo de cita desactivado en el catalogo mientras la
        # recepcionista tenia el dialog abierto no debe romper el check-in.
        tipo_cita = TipoDeCitas.objects.create(name="Consulta general")
        tipo_cita.is_active = False
        tipo_cita.save(update_fields=["is_active"])

        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP6002",
                "arrivalType": "walk_in",
                "tipoCitaId": tipo_cita.id,
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["tipoCitaId"], tipo_cita.id)
        self.assertEqual(response.data["tipoCitaNombre"], "Consulta general")

    def test_create_visit_without_tipo_cita_id_returns_null(self):
        self._login_as("recepcion_user", self.recepcion_password)

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP6003",
                "arrivalType": "walk_in",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["tipoCitaId"])
        self.assertIsNone(response.data["tipoCitaNombre"])
