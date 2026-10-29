import asyncio

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies, MotivoCita, Permisos, Roles
from apps.recepcion.models import Visit
from apps.realtime.consumers.visits import VISITS_STREAM_GROUP
from apps.realtime.events import (
    VISIT_EVENT_CANCELLED,
    VISIT_EVENT_CREATED,
    VISIT_EVENT_DIAGNOSIS_SAVED,
    VISIT_EVENT_NO_SHOW,
    VISIT_EVENT_PRESCRIPTIONS_SAVED,
    VISIT_EVENT_STATUS_CHANGED,
)
from apps.realtime.publisher import REALTIME_EVENT_HANDLER
from apps.realtime.schemas import ENVELOPE_VERSION
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


class VisitStreamRealtimeEventsApiTests(APITestCase):
    def setUp(self):
        self.request_id = "44444444-4444-4444-4444-444444444444"
        self.recepcion_password = "Recep_123456"
        self.clinico_password = "Clinico_123456"
        self.doctor_password = "Doctor_123456"

        self._create_user_with_role(
            username="recepcion_ws",
            email="recepcion_ws@example.com",
            password=self.recepcion_password,
            role_code="RECEPCION",
            landing_route="/recepcion/fichas/medicina-general",
            permissions=[
                "recepcion:fichas:medicina_general:read",
                "recepcion:fichas:medicina_general:create",
            ],
        )
        self._create_user_with_role(
            username="clinico_ws",
            email="clinico_ws@example.com",
            password=self.clinico_password,
            role_code="CLINICO",
            landing_route="/clinico/somatometria",
            permissions=["clinico:somatometria:read"],
        )
        self._create_user_with_role(
            username="doctor_ws",
            email="doctor_ws@example.com",
            password=self.doctor_password,
            role_code="DOCTOR",
            landing_route="/clinico/consultas/doctor",
        )

        self.visit_recepcion = Visit.objects.create(
            folio="WS-RCP-0001",
            patient=_paciente_de_llave("EXP91001", 0),
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id="APP-WS-0001",
            status="en_espera",
        )
        self.visit_somatometria = Visit.objects.create(
            folio="WS-SMT-0001",
            patient=_paciente_de_llave("EXP92001", 0),
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_somatometria",
        )
        self.visit_doctor_ready = Visit.objects.create(
            folio="WS-DOC-0001",
            patient=_paciente_de_llave("EXP93001", 0),
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id="APP-WS-0002",
            status="lista_para_doctor",
        )
        self.visit_doctor_open = Visit.objects.create(
            folio="WS-DOC-0002",
            patient=_paciente_de_llave("EXP93002", 0),
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id="APP-WS-0003",
            status="en_consulta",
        )

        # Motivo tipificado (catalogo cargado por la migracion de datos
        # catalogos/0021_motivos_cita); reemplaza el texto libre "motivo".
        self.motivo_cancelacion_id = MotivoCita.objects.get(
            name="Cancelada por el paciente"
        ).id

        CatCies.objects.create(
            code="A090",
            description="GASTROENTERITIS",
            version="CIE-10",
            is_active=True,
        )

    def _create_user_with_role(
        self,
        *,
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

    def _subscribe_visits_stream(self):
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)()
        async_to_sync(channel_layer.group_add)(VISITS_STREAM_GROUP, channel_name)
        return channel_layer, channel_name

    def _read_group_message(self, channel_layer, channel_name, timeout=1):
        async def _receive():
            return await asyncio.wait_for(channel_layer.receive(channel_name), timeout=timeout)

        return async_to_sync(_receive)()

    def _read_group_messages(self, channel_layer, channel_name, count, timeout=1):
        return [
            self._read_group_message(channel_layer, channel_name, timeout=timeout)
            for _ in range(count)
        ]

    def _unsubscribe_visits_stream(self, channel_layer, channel_name):
        async_to_sync(channel_layer.group_discard)(VISITS_STREAM_GROUP, channel_name)

    def _assert_event_envelope(self, event, *, expected_event_type, expected_entity_id):
        self.assertEqual(event.get("eventType"), expected_event_type)
        self.assertEqual(event.get("entity"), "visit")
        self.assertEqual(event.get("entityId"), str(expected_entity_id))
        self.assertEqual(event.get("version"), ENVELOPE_VERSION)
        self.assertEqual(event.get("requestId"), self.request_id)
        self.assertEqual(event.get("correlationId"), self.request_id)
        self.assertIsInstance(event.get("sequence"), int)
        self.assertGreater(event.get("sequence"), 0)

    def _assert_messages_envelope_and_order(self, messages):
        events = [message.get("event") or {} for message in messages]
        for message in messages:
            self.assertEqual(message.get("type"), REALTIME_EVENT_HANDLER)

        sequences = [event.get("sequence") for event in events]
        self.assertEqual(len(sequences), len(set(sequences)))
        self.assertEqual(sequences, sorted(sequences))

        return events

    def test_create_visit_publishes_created_and_status_changed_events(self):
        self._login_as("recepcion_ws", self.recepcion_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            "/api/v1/visits",
            {
                "patientId": 91555,
                "arrivalType": "appointment",
                "appointmentId": "APP-WS-CREATE",
                "doctorId": 77,
                "notes": "visita creada para prueba realtime",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        messages = self._read_group_messages(channel_layer, channel_name, count=2)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        events = self._assert_messages_envelope_and_order(messages)
        event_types = {event.get("eventType") for event in events}
        self.assertEqual(event_types, {VISIT_EVENT_CREATED, VISIT_EVENT_STATUS_CHANGED})

        for event in events:
            self._assert_event_envelope(
                event,
                expected_event_type=event.get("eventType"),
                expected_entity_id=response.data["id"],
            )

        created_event = next(
            event for event in events if event.get("eventType") == VISIT_EVENT_CREATED
        )
        self.assertEqual(created_event.get("payload", {}).get("status"), "en_espera")

        status_changed_event = next(
            event for event in events if event.get("eventType") == VISIT_EVENT_STATUS_CHANGED
        )
        self.assertEqual(status_changed_event.get("payload", {}).get("status"), "en_espera")
        self.assertIsNone(status_changed_event.get("payload", {}).get("previousStatus"))

    def test_patch_visit_status_cancelled_publishes_cancelled_and_status_changed_events(self):
        self._login_as("recepcion_ws", self.recepcion_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.patch(
            f"/api/v1/visits/{self.visit_recepcion.id_visit}/status",
            {
                "targetStatus": "cancelada",
                "motivoCancelacionId": self.motivo_cancelacion_id,
                "motivoDetalle": "El paciente solicito cancelar.",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        messages = self._read_group_messages(channel_layer, channel_name, count=2)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        events = self._assert_messages_envelope_and_order(messages)
        event_types = {event.get("eventType") for event in events}
        self.assertEqual(event_types, {VISIT_EVENT_CANCELLED, VISIT_EVENT_STATUS_CHANGED})

        for event in events:
            self._assert_event_envelope(
                event,
                expected_event_type=event.get("eventType"),
                expected_entity_id=self.visit_recepcion.id_visit,
            )

        cancelled_event = next(
            event for event in events if event.get("eventType") == VISIT_EVENT_CANCELLED
        )
        self.assertEqual(cancelled_event.get("payload", {}).get("status"), "cancelada")

        status_changed_event = next(
            event for event in events if event.get("eventType") == VISIT_EVENT_STATUS_CHANGED
        )
        self.assertEqual(status_changed_event.get("payload", {}).get("status"), "cancelada")
        self.assertEqual(
            status_changed_event.get("payload", {}).get("previousStatus"),
            "en_espera",
        )

    def test_patch_visit_status_no_show_publishes_no_show_and_status_changed_events(self):
        self._login_as("recepcion_ws", self.recepcion_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.patch(
            f"/api/v1/visits/{self.visit_recepcion.id_visit}/status",
            {"targetStatus": "no_show"},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        messages = self._read_group_messages(channel_layer, channel_name, count=2)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        events = self._assert_messages_envelope_and_order(messages)
        event_types = {event.get("eventType") for event in events}
        self.assertEqual(event_types, {VISIT_EVENT_NO_SHOW, VISIT_EVENT_STATUS_CHANGED})

        for event in events:
            self._assert_event_envelope(
                event,
                expected_event_type=event.get("eventType"),
                expected_entity_id=self.visit_recepcion.id_visit,
            )

        no_show_event = next(
            event for event in events if event.get("eventType") == VISIT_EVENT_NO_SHOW
        )
        self.assertEqual(no_show_event.get("payload", {}).get("status"), "no_show")

        status_changed_event = next(
            event for event in events if event.get("eventType") == VISIT_EVENT_STATUS_CHANGED
        )
        self.assertEqual(status_changed_event.get("payload", {}).get("status"), "no_show")
        self.assertEqual(
            status_changed_event.get("payload", {}).get("previousStatus"),
            "en_espera",
        )

    def test_create_visit_publishes_created_and_status_changed_events(self):
        self._login_as("recepcion_ws", self.recepcion_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            "/api/v1/visits",
            {
                "noExp": "EXP94001",
                "arrivalType": "appointment",
                "appointmentId": "APP-WS-94001",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        first_message = self._read_group_message(channel_layer, channel_name)
        second_message = self._read_group_message(channel_layer, channel_name)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        first_event = first_message.get("event") or {}
        second_event = second_message.get("event") or {}
        event_types = {first_event.get("eventType"), second_event.get("eventType")}

        self.assertEqual(event_types, {"visit.created", "visit.status.changed"})
        for event in (first_event, second_event):
            self.assertEqual(event.get("entity"), "visit")
            self.assertEqual(event.get("requestId"), self.request_id)
            self.assertEqual(event.get("payload", {}).get("status"), "en_espera")

    def test_capture_vitals_publishes_status_changed_event(self):
        self._login_as("clinico_ws", self.clinico_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            f"/api/v1/visits/{self.visit_somatometria.id_visit}/vitals",
            {
                "weightKg": 72,
                "heightCm": 175,
                "temperatureC": 36.6,
                "oxygenSaturationPct": 98,
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        message = self._read_group_message(channel_layer, channel_name)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        self.assertEqual(message.get("type"), REALTIME_EVENT_HANDLER)
        event = message.get("event") or {}
        self._assert_event_envelope(
            event,
            expected_event_type=VISIT_EVENT_STATUS_CHANGED,
            expected_entity_id=self.visit_somatometria.id_visit,
        )
        self.assertEqual(event.get("payload", {}).get("status"), "lista_para_doctor")
        self.assertEqual(
            event.get("payload", {}).get("previousStatus"),
            "en_somatometria",
        )

    def test_start_consultation_publishes_status_changed_event(self):
        self._login_as("doctor_ws", self.doctor_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            f"/api/v1/visits/{self.visit_doctor_ready.id_visit}/consultation/start",
            {},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        message = self._read_group_message(channel_layer, channel_name)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        self.assertEqual(message.get("type"), REALTIME_EVENT_HANDLER)
        event = message.get("event") or {}
        self._assert_event_envelope(
            event,
            expected_event_type=VISIT_EVENT_STATUS_CHANGED,
            expected_entity_id=self.visit_doctor_ready.id_visit,
        )
        self.assertEqual(event.get("payload", {}).get("status"), "en_consulta")

    def test_close_consultation_publishes_visit_closed_event(self):
        self._login_as("doctor_ws", self.doctor_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            f"/api/v1/visits/{self.visit_doctor_open.id_visit}/consultation/close",
            {
                "primaryDiagnosis": "Rinofaringitis",
                "finalNote": "Alta con manejo ambulatorio.",
                # Obligatorios al cerrar la consulta (serializer / consultation_usecase).
                "cieCode": "A090",
                "morbidity": "1",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        message = self._read_group_message(channel_layer, channel_name)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        self.assertEqual(message.get("type"), REALTIME_EVENT_HANDLER)
        event = message.get("event") or {}
        self._assert_event_envelope(
            event,
            expected_event_type="visit.closed",
            expected_entity_id=self.visit_doctor_open.id_visit,
        )
        self.assertEqual(event.get("payload"), {})

    def test_save_diagnosis_publishes_diagnosis_saved_event(self):
        self._login_as("doctor_ws", self.doctor_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            f"/api/v1/visits/{self.visit_doctor_open.id_visit}/diagnosis",
            {
                "primaryDiagnosis": "Lumbalgia mecanica",
                "finalNote": "Manejo sintomatico ambulatorio.",
                "cieCode": "A090",
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        message = self._read_group_message(channel_layer, channel_name)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        self.assertEqual(message.get("type"), REALTIME_EVENT_HANDLER)
        event = message.get("event") or {}
        self._assert_event_envelope(
            event,
            expected_event_type=VISIT_EVENT_DIAGNOSIS_SAVED,
            expected_entity_id=self.visit_doctor_open.id_visit,
        )
        self.assertEqual(
            event.get("payload", {}).get("primaryDiagnosis"),
            "Lumbalgia mecanica",
        )
        self.assertEqual(event.get("payload", {}).get("cieCode"), "A090")

    def test_save_prescriptions_publishes_prescriptions_saved_event(self):
        self._login_as("doctor_ws", self.doctor_password)
        channel_layer, channel_name = self._subscribe_visits_stream()

        response = self.client.post(
            f"/api/v1/visits/{self.visit_doctor_open.id_visit}/prescriptions",
            {
                "items": [
                    "Paracetamol 500mg cada 8h por 3 dias",
                    "Reposo domiciliario",
                ]
            },
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        message = self._read_group_message(channel_layer, channel_name)
        self._unsubscribe_visits_stream(channel_layer, channel_name)

        self.assertEqual(message.get("type"), REALTIME_EVENT_HANDLER)
        event = message.get("event") or {}
        self._assert_event_envelope(
            event,
            expected_event_type=VISIT_EVENT_PRESCRIPTIONS_SAVED,
            expected_entity_id=self.visit_doctor_open.id_visit,
        )
        self.assertEqual(
            event.get("payload", {}).get("items"),
            [
                "Paracetamol 500mg cada 8h por 3 dias",
                "Reposo domiciliario",
            ],
        )
