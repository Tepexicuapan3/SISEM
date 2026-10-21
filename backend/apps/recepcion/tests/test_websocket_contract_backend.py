import asyncio

from asgiref.testing import ApplicationCommunicator
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings

from apps.administracion.models import RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import SyUsuario
from apps.authentication.services.token_service import ACCESS_COOKIE, create_access_refresh_tokens
from apps.catalogos.models import Roles
from apps.consulta_medica.services.realtime_events import (
    build_visit_closed_event,
)
from apps.recepcion.services.realtime_events import (
    build_visit_status_changed_event,
)
from config.asgi import application
from infrastructure.realtime.contracts import (
    validate_realtime_event_envelope,
)
from infrastructure.realtime.ordering import evaluate_sequence_progression
from infrastructure.realtime.ws_app import WS_VISITS_STREAM_PATH


@override_settings(
    ALLOWED_HOSTS=["localhost", "testserver"],
    WS_ALLOW_ALL_ORIGINS=False,
    WS_ALLOWED_ORIGINS="http://localhost:5173",
)
class VisitWebSocketContractsTests(TestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="ws_user",
            correo="ws_user@example.com",
            clave_hash=make_password("Secret123!"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        recepcion_role, _ = Roles.objects.get_or_create(
            rol="RECEPCION",
            defaults={
                "desc_rol": "Recepcion",
                "landing_route": "/recepcion/fichas/medicina-general",
                "is_active": True,
            },
        )
        RelUsuarioRol.objects.get_or_create(
            id_usuario=self.user,
            id_rol=recepcion_role,
            defaults={"is_primary": True},
        )

        self.admin_user = SyUsuario.objects.create(
            usuario="ws_admin_user",
            correo="ws_admin_user@example.com",
            clave_hash=make_password("Secret123!"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        admin_role, _ = Roles.objects.get_or_create(
            rol="ADMIN",
            defaults={
                "desc_rol": "Administracion",
                "landing_route": "/dashboard",
                "is_active": True,
                "is_admin": True,
            },
        )
        RelUsuarioRol.objects.get_or_create(
            id_usuario=self.admin_user,
            id_rol=admin_role,
            defaults={"is_primary": True},
        )

        # El handshake exige que el sid del token sea la sesion activa (Redis).
        access_token, _, user_sid = create_access_refresh_tokens(self.user)
        self.cookie_header = f"{ACCESS_COOKIE}={access_token}".encode()
        admin_access_token, _, admin_sid = create_access_refresh_tokens(self.admin_user)
        self.admin_cookie_header = f"{ACCESS_COOKIE}={admin_access_token}".encode()
        PolicyStore().set_active_session(self.user.id_usuario, user_sid, 600)
        PolicyStore().set_active_session(self.admin_user.id_usuario, admin_sid, 600)

    def test_handshake_requires_valid_cookie_auth(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.admin_cookie_header),
            ]
        )

        self.assertEqual(response["type"], "websocket.accept")

    def test_handshake_rejects_role_only_user_without_stream_capability(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.cookie_header),
            ]
        )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response["code"], 4403)

    def test_handshake_rejects_invalid_origin(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://evil.example"),
                (b"cookie", self.cookie_header),
            ]
        )

        self.assertEqual(response["type"], "websocket.close")

    def test_handshake_rejects_missing_auth_cookie(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
            ]
        )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response["code"], 4401)

    def test_event_envelope_v1_required_fields_and_types(self):
        recepcion_event = build_visit_status_changed_event(
            visit_id="VIS-1001",
            status="en_somatometria",
            sequence=1042,
            request_id="req-1001",
            correlation_id="corr-1001",
        )
        consulta_event = build_visit_closed_event(
            visit_id="VIS-1001",
            sequence=1043,
            request_id="req-1002",
            correlation_id="corr-1002",
        )

        validate_realtime_event_envelope(recepcion_event)
        validate_realtime_event_envelope(consulta_event)

        self.assertEqual(recepcion_event["version"], 1)
        self.assertIsInstance(recepcion_event["eventId"], str)
        self.assertIsInstance(recepcion_event["sequence"], int)
        self.assertGreater(recepcion_event["sequence"], 0)
        self.assertEqual(recepcion_event["entity"], "visit")

    def test_ordering_and_gap_semantics(self):
        first = evaluate_sequence_progression(last_sequence=None, incoming_sequence=1042)
        self.assertTrue(first.is_monotonic)
        self.assertFalse(first.has_gap)

        second = evaluate_sequence_progression(last_sequence=1042, incoming_sequence=1043)
        self.assertTrue(second.is_monotonic)
        self.assertFalse(second.has_gap)

        with_gap = evaluate_sequence_progression(last_sequence=1043, incoming_sequence=1045)
        self.assertTrue(with_gap.is_monotonic)
        self.assertTrue(with_gap.has_gap)
        self.assertEqual(with_gap.expected_sequence, 1044)

        out_of_order = evaluate_sequence_progression(last_sequence=1045, incoming_sequence=1044)
        self.assertFalse(out_of_order.is_monotonic)
        self.assertFalse(out_of_order.has_gap)

    def _connect_once(self, headers):
        async def run_connect():
            communicator = ApplicationCommunicator(
                application,
                {
                    "type": "websocket",
                    "path": WS_VISITS_STREAM_PATH,
                    "headers": headers,
                    "query_string": b"",
                    "subprotocols": [],
                },
            )

            await communicator.send_input({"type": "websocket.connect"})
            output = await communicator.receive_output(timeout=1)

            if output.get("type") == "websocket.accept":
                await communicator.send_input({"type": "websocket.disconnect", "code": 1000})

            await communicator.wait()
            return output

        return asyncio.run(run_connect())
