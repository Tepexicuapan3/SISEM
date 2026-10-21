import asyncio
from unittest.mock import patch

from asgiref.testing import ApplicationCommunicator
from channels.layers import get_channel_layer
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings

from apps.administracion.models import RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import SyUsuario
from apps.authentication.services.errors import PolicyStoreUnavailableError
from apps.authentication.services.session_revocation import revoke_user_sessions
from apps.catalogos.models import Roles
from apps.authentication.services.token_service import (
    ACCESS_COOKIE,
    create_access_refresh_tokens,
)
from apps.realtime.routing import WS_VISITS_STREAM_PATH
from config.asgi import application


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    ALLOWED_HOSTS=["localhost", "testserver"],
    WS_ALLOW_ALL_ORIGINS=False,
    WS_ALLOWED_ORIGINS="http://localhost:5173",
)
class RealtimeHandshakeSecurityTests(TestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="ws_realtime_user",
            correo="ws_realtime_user@example.com",
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
        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=recepcion_role,
            is_primary=True,
        )

        self.user_without_stream_role = SyUsuario.objects.create(
            usuario="ws_no_role",
            correo="ws_no_role@example.com",
            clave_hash=make_password("Secret123!"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
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
        RelUsuarioRol.objects.create(
            id_usuario=self.admin_user,
            id_rol=admin_role,
            is_primary=True,
        )

        # El handshake exige que el sid del token sea la sesion activa (Redis).
        self.policy_store = PolicyStore()
        access_token, _, self.user_sid = create_access_refresh_tokens(self.user)
        self.cookie_header = f"{ACCESS_COOKIE}={access_token}".encode()
        blocked_token, _, blocked_sid = create_access_refresh_tokens(
            self.user_without_stream_role
        )
        self.blocked_cookie_header = f"{ACCESS_COOKIE}={blocked_token}".encode()
        admin_token, _, self.admin_sid = create_access_refresh_tokens(self.admin_user)
        self.admin_cookie_header = f"{ACCESS_COOKIE}={admin_token}".encode()
        for user, sid in (
            (self.user, self.user_sid),
            (self.user_without_stream_role, blocked_sid),
            (self.admin_user, self.admin_sid),
        ):
            self.policy_store.set_active_session(user.id_usuario, sid, 600)

    def _admin_headers(self):
        return [
            (b"origin", b"http://localhost:5173"),
            (b"cookie", self.admin_cookie_header),
        ]

    # R6-S1/S2: sesion revocada (revoke_user_sessions) -> rechazo 4401.
    def test_connection_rejects_revoked_session(self):
        revoke_user_sessions(self.admin_user)

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    # R6-S3
    def test_connection_rejects_inactive_user(self):
        self.admin_user.est_activo = False
        self.admin_user.save(update_fields=["est_activo"])

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_blocked_user(self):
        self.admin_user.est_bloqueado = True
        self.admin_user.save(update_fields=["est_bloqueado"])

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_user_with_pending_password_change(self):
        self.admin_user.cambiar_clave = True
        self.admin_user.save(update_fields=["cambiar_clave"])

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_user_with_terms_not_accepted(self):
        self.admin_user.terminos_acept = False
        self.admin_user.save(update_fields=["terminos_acept"])

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    # R6-S4: login en otro equipo reemplaza el sid activo.
    def test_connection_rejects_sid_replaced_by_another_session(self):
        self.policy_store.set_active_session(
            self.admin_user.id_usuario, "otro-sid-reemplazo", 600
        )

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_when_no_active_session_in_store(self):
        self.policy_store.clear_active_session(self.admin_user.id_usuario)

        response = self._connect_once(headers=self._admin_headers(), query_string=b"")

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_token_without_sid(self):
        payload = {"user_id": str(self.admin_user.id_usuario)}
        with patch(
            "apps.realtime.auth.decode_access_token", return_value=payload
        ):
            response = self._connect_once(
                headers=self._admin_headers(), query_string=b""
            )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    # R6-S5: Redis caido -> fail-open con warning.
    def test_connection_fail_open_when_redis_is_down(self):
        with patch(
            "apps.realtime.auth.policy_store.get_active_session",
            side_effect=PolicyStoreUnavailableError("down"),
        ):
            with self.assertLogs("apps.realtime.auth", level="WARNING") as logs:
                response = self._connect_once(
                    headers=self._admin_headers(), query_string=b""
                )

        self.assertEqual(response["type"], "websocket.accept")
        self.assertTrue(
            any("WS_SESSION_CHECK_REDIS_UNAVAILABLE" in line for line in logs.output)
        )

    # Corte inmediato: group event session.revoked -> close 4401.
    def test_open_socket_is_closed_with_4401_on_session_revoked_event(self):
        user_id = self.admin_user.id_usuario

        async def run():
            communicator = ApplicationCommunicator(
                application,
                {
                    "type": "websocket",
                    "path": WS_VISITS_STREAM_PATH,
                    "headers": self._admin_headers(),
                    "query_string": b"",
                    "subprotocols": [],
                },
            )
            await communicator.send_input({"type": "websocket.connect"})
            accepted = await communicator.receive_output(timeout=1)
            self.assertEqual(accepted["type"], "websocket.accept")

            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"user.{user_id}", {"type": "session.revoked"}
            )
            closed = await communicator.receive_output(timeout=1)
            await communicator.wait()
            return closed

        closed = asyncio.run(run())

        self.assertEqual(closed["type"], "websocket.close")
        self.assertEqual(closed.get("code"), 4401)

    def test_session_revoked_event_does_not_close_other_users_socket(self):
        other_id = self.user.id_usuario

        async def run():
            communicator = ApplicationCommunicator(
                application,
                {
                    "type": "websocket",
                    "path": WS_VISITS_STREAM_PATH,
                    "headers": self._admin_headers(),
                    "query_string": b"",
                    "subprotocols": [],
                },
            )
            await communicator.send_input({"type": "websocket.connect"})
            accepted = await communicator.receive_output(timeout=1)
            self.assertEqual(accepted["type"], "websocket.accept")

            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"user.{other_id}", {"type": "session.revoked"}
            )
            await communicator.send_input({"type": "websocket.disconnect", "code": 1000})
            await communicator.wait()
            return True

        self.assertTrue(asyncio.run(run()))

    def test_connection_accepts_valid_cookie_auth(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.admin_cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.accept")

    def test_connection_accepts_admin_with_wildcard_permissions(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.admin_cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.accept")

    @override_settings(
        DEBUG=True,
        ALLOW_ALL_HOSTS=True,
        WS_ALLOW_ALL_ORIGINS=False,
        WS_ALLOWED_ORIGINS="",
    )
    def test_connection_accepts_origin_when_debug_allow_all_hosts_enabled(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.admin_cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.accept")

    @override_settings(
        DEBUG=False,
        WS_ALLOW_ALL_ORIGINS=False,
        WS_ALLOWED_ORIGINS="",
        ALLOWED_HOSTS=["localhost", "testserver"],
    )
    def test_connection_accepts_origin_matching_allowed_hosts_fallback(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.admin_cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.accept")

    def test_connection_rejects_missing_auth_cookie(self):
        response = self._connect_once(
            headers=[(b"origin", b"http://localhost:5173")],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_not_allowed_origin(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://evil.example"),
                (b"cookie", self.admin_cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.close")

    def test_connection_rejects_token_in_query_string(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.admin_cookie_header),
            ],
            query_string=b"access_token=forbidden-token",
        )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4401)

    def test_connection_rejects_authenticated_user_without_stream_access(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.blocked_cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4403)

    def test_connection_rejects_role_only_user_without_stream_capability(self):
        response = self._connect_once(
            headers=[
                (b"origin", b"http://localhost:5173"),
                (b"cookie", self.cookie_header),
            ],
            query_string=b"",
        )

        self.assertEqual(response["type"], "websocket.close")
        self.assertEqual(response.get("code"), 4403)

    def _connect_once(self, *, headers, query_string):
        async def run_connect():
            communicator = ApplicationCommunicator(
                application,
                {
                    "type": "websocket",
                    "path": WS_VISITS_STREAM_PATH,
                    "headers": headers,
                    "query_string": query_string,
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
