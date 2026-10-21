import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.authentication.application.auth_policy_service import AuthPolicyService
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SesionUsuario, SyUsuario
from apps.authentication.services.errors import PolicyStoreUnavailableError
from apps.authentication.services.login_unlock import unlock_login
from apps.authentication.services.session_registry import start_session
from apps.authentication.services.session_revocation import (
    revoke_user_sessions,
    rotate_user_session,
)

MODULE = "apps.authentication.services.session_revocation"


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    },
)
class SessionRevocationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.store = PolicyStore()
        self.user = SyUsuario.objects.create(
            usuario="revoke_user",
            correo="revoke.user@example.com",
            clave_hash=make_password("Revoke_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user, nombre="Revoke", paterno="User", materno=""
        )

    def _open_session(self, sid):
        return SesionUsuario.objects.create(usuario=self.user, session_id=sid)

    # R1-S1
    def test_revoke_clears_redis_and_closes_open_rows(self):
        self.store.set_active_session(self.user.id_usuario, "sid-2", 600)
        first = self._open_session("sid-1")
        second = self._open_session("sid-2")

        result = revoke_user_sessions(self.user)

        self.assertTrue(result)
        self.assertIsNone(self.store.get_active_session(self.user.id_usuario))
        for row in (first, second):
            row.refresh_from_db()
            self.assertIsNotNone(row.fch_fin)
            self.assertEqual(row.cerrada_por, SesionUsuario.CierrePor.REVOCADA)

    # R1-S2 (idempotente)
    def test_revoke_without_active_session_is_noop_and_idempotent(self):
        self.assertTrue(revoke_user_sessions(self.user))
        self.assertTrue(revoke_user_sessions(self.user))
        self.assertEqual(SesionUsuario.objects.filter(usuario=self.user).count(), 0)

    def test_revoke_twice_keeps_first_close_data(self):
        row = self._open_session("sid-1")
        revoke_user_sessions(self.user)
        row.refresh_from_db()
        first_fin = row.fch_fin

        revoke_user_sessions(self.user)

        row.refresh_from_db()
        self.assertEqual(row.fch_fin, first_fin)

    # R1-S3
    def test_revoke_is_fail_soft_when_redis_is_down(self):
        row = self._open_session("sid-1")

        with patch(
            f"{MODULE}.policy_store.clear_active_session",
            side_effect=PolicyStoreUnavailableError("down"),
        ):
            with self.assertLogs(MODULE, level="WARNING") as logs:
                result = revoke_user_sessions(self.user)

        self.assertFalse(result)
        row.refresh_from_db()
        self.assertEqual(row.cerrada_por, SesionUsuario.CierrePor.REVOCADA)
        self.assertIsNotNone(row.fch_fin)
        self.assertTrue(
            any("SESSION_REVOKE_REDIS_UNAVAILABLE" in line for line in logs.output)
        )

    # R1-S4
    def test_revoke_does_not_touch_already_closed_rows(self):
        closed = self._open_session("sid-old")
        SesionUsuario.objects.filter(pk=closed.pk).update(
            fch_fin=closed.fch_inicio, cerrada_por=SesionUsuario.CierrePor.LOGOUT
        )

        revoke_user_sessions(self.user)

        closed.refresh_from_db()
        self.assertEqual(closed.cerrada_por, SesionUsuario.CierrePor.LOGOUT)

    def test_revoke_only_affects_target_user(self):
        other = SyUsuario.objects.create(
            usuario="other_user",
            correo="other.user@example.com",
            clave_hash=make_password("Other_123456"),
            est_activo=True,
        )
        other_row = SesionUsuario.objects.create(usuario=other, session_id="sid-other")
        self.store.set_active_session(other.id_usuario, "sid-other", 600)

        revoke_user_sessions(self.user)

        other_row.refresh_from_db()
        self.assertIsNone(other_row.fch_fin)
        self.assertEqual(self.store.get_active_session(other.id_usuario), "sid-other")

    # Orden: filas DB antes que Redis (carrera con el barrido de abandonadas)
    def test_revoke_closes_db_rows_before_clearing_redis(self):
        row = self._open_session("sid-1")
        observed = {}

        def _clear(user_id):
            row.refresh_from_db()
            observed["closed_before_redis"] = row.fch_fin is not None

        with patch(f"{MODULE}.policy_store.clear_active_session", side_effect=_clear):
            revoke_user_sessions(self.user)

        self.assertTrue(observed["closed_before_redis"])

    # WS: group_send session.revoked a user.{id}
    def test_revoke_notifies_user_group_with_session_revoked_event(self):
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)()
        async_to_sync(channel_layer.group_add)(
            f"user.{self.user.id_usuario}", channel_name
        )

        revoke_user_sessions(self.user)

        async def _receive():
            return await asyncio.wait_for(
                channel_layer.receive(channel_name), timeout=1
            )

        message = async_to_sync(_receive)()
        self.assertEqual(message["type"], "session.revoked")

    def test_revoke_group_send_targets_per_user_group(self):
        layer = MagicMock()
        layer.group_send = AsyncMock()

        with patch(f"{MODULE}.get_channel_layer", return_value=layer):
            revoke_user_sessions(self.user)

        layer.group_send.assert_called_once_with(
            f"user.{self.user.id_usuario}", {"type": "session.revoked"}
        )

    def test_revoke_does_not_raise_when_channel_layer_fails(self):
        row = self._open_session("sid-1")

        with patch(f"{MODULE}.get_channel_layer", side_effect=RuntimeError("boom")):
            result = revoke_user_sessions(self.user)

        self.assertTrue(result)
        row.refresh_from_db()
        self.assertEqual(row.cerrada_por, SesionUsuario.CierrePor.REVOCADA)

    def test_revoke_without_channel_layer_is_noop(self):
        with patch(f"{MODULE}.get_channel_layer", return_value=None):
            self.assertTrue(revoke_user_sessions(self.user))

    # rotate_user_session
    def test_rotate_replaces_active_session_with_new_sid(self):
        _a, _r, old_sid = start_session(self.user, "127.0.0.1", "ua")

        access, refresh, new_sid = rotate_user_session(self.user, "127.0.0.1", "ua")

        self.assertTrue(access)
        self.assertTrue(refresh)
        self.assertNotEqual(old_sid, new_sid)
        self.assertEqual(self.store.get_active_session(self.user.id_usuario), new_sid)
        old_row = SesionUsuario.objects.get(usuario=self.user, session_id=old_sid)
        self.assertEqual(old_row.cerrada_por, SesionUsuario.CierrePor.REVOCADA)
        open_rows = SesionUsuario.objects.filter(usuario=self.user, fch_fin__isnull=True)
        self.assertEqual(open_rows.count(), 1)
        self.assertEqual(open_rows.first().session_id, new_sid)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class LoginUnlockTests(TestCase):
    def setUp(self):
        cache.clear()
        self.store = PolicyStore()
        self.user = SyUsuario.objects.create(
            usuario="Unlock_User",
            correo="unlock.user@example.com",
            clave_hash=make_password("Unlock_123456"),
            est_activo=True,
        )

    def test_unlock_clears_account_counter_and_lock(self):
        username_key = self.user.usuario.lower()
        lock_key = AuthPolicyService._login_account_lock_key(username_key)
        counter_key = AuthPolicyService._login_account_counter_key(username_key)
        self.store.set_lock(lock_key, 600)
        self.store.increment_counter(counter_key, 600)

        unlock_login(self.user)

        self.assertFalse(self.store.is_locked(lock_key))
        self.assertEqual(self.store.get_counter(counter_key), 0)

    def test_unlock_is_idempotent_when_not_locked(self):
        unlock_login(self.user)
        unlock_login(self.user)

    def test_unlock_does_not_touch_other_accounts(self):
        other_key = AuthPolicyService._login_account_lock_key("someone_else")
        self.store.set_lock(other_key, 600)

        unlock_login(self.user)

        self.assertTrue(self.store.is_locked(other_key))

    def test_unlock_propagates_policy_store_unavailable(self):
        with patch(
            "apps.authentication.services.login_unlock.policy_store.clear_counter",
            side_effect=PolicyStoreUnavailableError("down"),
        ):
            with self.assertRaises(PolicyStoreUnavailableError):
                unlock_login(self.user)
