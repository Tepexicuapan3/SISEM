from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError

from apps.authentication.models import DetUsuario, SesionUsuario, SyUsuario
from apps.authentication.services.errors import (
    AuthServiceError,
    PolicyStoreUnavailableError,
)
from apps.authentication.services.reset_token_guard import (
    consume_reset_jti,
    ensure_user_can_reset,
)
from apps.authentication.services.session_registry import start_session
from apps.authentication.services.otp_service import OTP_TTL_SECONDS
from apps.authentication.services.token_service import create_reset_token
from apps.authentication.uses_case.change_password_usecase import change_password
from apps.authentication.uses_case.onboarding_usecase import complete_onboarding
from apps.authentication.uses_case.refresh_usecase import refresh_tokens
from apps.authentication.uses_case.request_reset_code_usecase import request_reset_code
from apps.authentication.uses_case.reset_password_usecase import reset_password
from apps.authentication.uses_case.verify_reset_code_usecase import verify_reset_code


class AuthUseCasesTests(TestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="usecase_user",
            correo="usecase.user@example.com",
            clave_hash=make_password("Usecase_123456"),
            est_activo=True,
            cambiar_clave=True,
            terminos_acept=False,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Usecase",
            paterno="User",
            materno="",
        )

    @patch("apps.authentication.uses_case.onboarding_usecase.validate_password")
    def test_complete_onboarding_password_too_weak_raises(self, validate_mock):
        validate_mock.side_effect = ValidationError(["weak"])

        with self.assertRaises(AuthServiceError) as ctx:
            complete_onboarding(self.user, "weak", True, "127.0.0.1")

        self.assertEqual(ctx.exception.code, "PASSWORD_TOO_WEAK")

    def test_complete_onboarding_requires_terms(self):
        with self.assertRaises(AuthServiceError) as ctx:
            complete_onboarding(self.user, "Valida_123456", False, "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TERMS_NOT_ACCEPTED")

    def test_complete_onboarding_already_completed_path(self):
        self.user.cambiar_clave = False
        self.user.terminos_acept = True
        self.user.save(update_fields=["cambiar_clave", "terminos_acept"])

        result = complete_onboarding(self.user, "Valida_123456", True, "127.0.0.1")

        self.assertIn("user", result)
        self.assertIn("access_token", result)
        self.assertIn("refresh_token", result)

    @patch(
        "apps.authentication.uses_case.request_reset_code_usecase.policy_service.check_reset_request"
    )
    def test_request_reset_code_rate_limit(self, check_reset_request_mock):
        check_reset_request_mock.side_effect = AuthServiceError(
            "RATE_LIMIT_EXCEEDED",
            "Demasiadas solicitudes, espera un momento",
            429,
        )

        with self.assertRaises(AuthServiceError) as ctx:
            request_reset_code("usecase.user@example.com")

        self.assertEqual(ctx.exception.code, "RATE_LIMIT_EXCEEDED")

    @patch(
        "apps.authentication.uses_case.request_reset_code_usecase.send_reset_code_email"
    )
    @patch("apps.authentication.uses_case.request_reset_code_usecase.generate_code")
    def test_request_reset_code_uses_username_when_no_profile_name(
        self, code_mock, send_mock
    ):
        self.user.detalle.nombre = ""
        self.user.detalle.paterno = ""
        self.user.detalle.materno = ""
        self.user.detalle.save()

        code_mock.return_value = "123456"
        send_mock.return_value = True

        request_reset_code("usecase.user@example.com")

        send_mock.assert_called_once()
        args, kwargs = send_mock.call_args
        self.assertEqual(args[0], "usecase.user@example.com")
        self.assertEqual(kwargs["user_name"], "usecase_user")

    @patch("apps.authentication.uses_case.reset_password_usecase.decode_reset_token")
    def test_reset_password_invalid_token_error(self, decode_mock):
        decode_mock.side_effect = TokenError("invalid token")

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password("bad-token", "Nueva_123456", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")

    @patch("apps.authentication.uses_case.reset_password_usecase.decode_reset_token")
    def test_reset_password_expired_token_error(self, decode_mock):
        decode_mock.side_effect = TokenError("token expired")

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password("expired-token", "Nueva_123456", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TOKEN_EXPIRED")

    @patch("apps.authentication.uses_case.reset_password_usecase.decode_reset_token")
    def test_reset_password_user_not_found(self, decode_mock):
        decode_mock.return_value = {"user_id": "999999"}

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password("token", "Nueva_123456", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "USER_NOT_FOUND")

    @patch("apps.authentication.uses_case.reset_password_usecase.validate_password")
    def test_reset_password_password_too_weak(self, validate_mock):
        token = create_reset_token(self.user)
        validate_mock.side_effect = ValidationError(["weak"])

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password(token, "corta", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "PASSWORD_TOO_WEAK")

    def test_verify_reset_code_user_not_found_after_valid_code(self):
        from apps.authentication.services.otp_service import store_code

        store_code("ghost.user@example.com", "123456")
        with self.assertRaises(AuthServiceError) as ctx:
            verify_reset_code("ghost.user@example.com", "123456")

        self.assertEqual(ctx.exception.code, "CODE_EXPIRED")

    def test_verify_reset_code_consumes_otp_as_one_time_token(self):
        from apps.authentication.services.otp_service import store_code

        email = "usecase.user@example.com"
        store_code(email, "123456")

        first_result = verify_reset_code(email, "123456")
        self.assertTrue(first_result["valid"])

        with self.assertRaises(AuthServiceError) as ctx:
            verify_reset_code(email, "123456")

        self.assertEqual(ctx.exception.code, "CODE_EXPIRED")

    def test_verify_reset_code_when_attempt_limit_already_reached(self):
        from apps.authentication.application.auth_policy_service import (
            AuthPolicyService,
        )
        from apps.authentication.services.otp_service import store_code

        email = "usecase.user@example.com"
        store_code(email, "123456")
        policy_service = AuthPolicyService()
        for _ in range(5):
            policy_service.record_verify_failure(email)

        with self.assertRaises(AuthServiceError) as ctx:
            verify_reset_code(email, "123456")

        self.assertEqual(ctx.exception.code, "ACCOUNT_LOCKED")

    def test_refresh_tokens_session_expired_for_inactive_user(self):
        # Use refresh token normal para este flujo
        from apps.authentication.services.token_service import (
            create_access_refresh_tokens,
        )

        _, refresh, _sid = create_access_refresh_tokens(self.user)
        self.user.est_activo = False
        self.user.save(update_fields=["est_activo"])

        with self.assertRaises(AuthServiceError) as ctx:
            refresh_tokens(refresh)

        self.assertEqual(ctx.exception.code, "SESSION_EXPIRED")

    def test_otp_ttl_is_five_minutes(self):
        self.assertEqual(OTP_TTL_SECONDS, 300)

    @patch("apps.authentication.uses_case.change_password_usecase.validate_password")
    def test_change_password_updates_hash_when_current_password_is_valid(
        self, validate_password_mock
    ):
        validate_password_mock.return_value = None

        change_password(self.user, "Usecase_123456", "Nueva_123456")

        self.user.refresh_from_db()
        self.assertTrue(check_password("Nueva_123456", self.user.clave_hash))

    def test_change_password_invalid_current_password(self):
        with self.assertRaises(AuthServiceError) as ctx:
            change_password(self.user, "ClaveMala1", "Nueva_123456")

        self.assertEqual(ctx.exception.code, "INVALID_CREDENTIALS")

    @patch("apps.authentication.uses_case.change_password_usecase.validate_password")
    def test_change_password_rejects_same_password(self, validate_password_mock):
        validate_password_mock.return_value = None

        with self.assertRaises(AuthServiceError) as ctx:
            change_password(self.user, "Usecase_123456", "Usecase_123456")

        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    @patch("apps.authentication.uses_case.change_password_usecase.validate_password")
    def test_change_password_password_too_weak(self, validate_password_mock):
        validate_password_mock.side_effect = ValidationError(["weak"])

        with self.assertRaises(AuthServiceError) as ctx:
            change_password(self.user, "Usecase_123456", "corta")

        self.assertEqual(ctx.exception.code, "PASSWORD_TOO_WEAK")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class ResetPasswordHardeningTests(TestCase):
    """auth-session-revocation: reset token de un solo uso + estado del usuario."""

    def setUp(self):
        cache.clear()
        self.user = SyUsuario.objects.create(
            usuario="reset_hardening",
            correo="reset.hardening@example.com",
            clave_hash=make_password("Reset_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user, nombre="Reset", paterno="Hardening", materno=""
        )

    def _password_unchanged(self):
        self.user.refresh_from_db()
        return check_password("Reset_123456", self.user.clave_hash)

    # R5-S1
    def test_reset_password_token_is_single_use(self):
        token = create_reset_token(self.user)

        result = reset_password(token, "Nueva_Clave_123", "127.0.0.1")
        self.assertIn("access_token", result)

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password(token, "Otra_Clave_456", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")
        self.assertEqual(ctx.exception.status_code, 401)
        self.user.refresh_from_db()
        self.assertTrue(check_password("Nueva_Clave_123", self.user.clave_hash))

    # R5-S2
    def test_reset_password_rejects_inactive_user(self):
        token = create_reset_token(self.user)
        self.user.est_activo = False
        self.user.save(update_fields=["est_activo"])

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password(token, "Nueva_Clave_123", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")
        self.assertTrue(self._password_unchanged())

    def test_reset_password_rejects_user_with_fch_baja(self):
        token = create_reset_token(self.user)
        self.user.fch_baja = timezone.now()
        self.user.save(update_fields=["fch_baja"])

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password(token, "Nueva_Clave_123", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")
        self.assertTrue(self._password_unchanged())

    def test_reset_password_rejects_blocked_user(self):
        token = create_reset_token(self.user)
        self.user.est_bloqueado = True
        self.user.save(update_fields=["est_bloqueado"])

        with self.assertRaises(AuthServiceError) as ctx:
            reset_password(token, "Nueva_Clave_123", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")
        self.assertTrue(self._password_unchanged())

    def test_reset_password_rejected_for_inactive_user_does_not_consume_jti(self):
        # El estado se valida antes de consumir: el jti no se quema.
        token = create_reset_token(self.user)
        self.user.est_activo = False
        self.user.save(update_fields=["est_activo"])
        with self.assertRaises(AuthServiceError):
            reset_password(token, "Nueva_Clave_123", "127.0.0.1")

        self.user.est_activo = True
        self.user.save(update_fields=["est_activo"])

        result = reset_password(token, "Nueva_Clave_123", "127.0.0.1")
        self.assertIn("access_token", result)

    # R5-S3
    def test_reset_password_fail_closed_when_jti_store_unavailable(self):
        token = create_reset_token(self.user)

        with patch(
            "apps.authentication.services.reset_token_guard.reset_token_store.mark_consumed",
            side_effect=PolicyStoreUnavailableError("down"),
        ):
            with self.assertRaises(AuthServiceError) as ctx:
                reset_password(token, "Nueva_Clave_123", "127.0.0.1")

        self.assertEqual(ctx.exception.code, "SERVICE_UNAVAILABLE")
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertTrue(self._password_unchanged())

    # R5-S4: password debil no quema el token
    def test_reset_password_weak_password_does_not_burn_token(self):
        token = create_reset_token(self.user)

        with patch(
            "apps.authentication.uses_case.reset_password_usecase.validate_password",
            side_effect=ValidationError(["weak"]),
        ):
            with self.assertRaises(AuthServiceError) as ctx:
                reset_password(token, "corta", "127.0.0.1")
        self.assertEqual(ctx.exception.code, "PASSWORD_TOO_WEAK")

        result = reset_password(token, "Nueva_Clave_123", "127.0.0.1")
        self.assertIn("access_token", result)

    # R5-S6
    def test_reset_password_closes_previous_sessions_and_opens_single_new_one(self):
        _a, _r, old_sid = start_session(self.user, "127.0.0.1", "ua")
        token = create_reset_token(self.user)

        reset_password(token, "Nueva_Clave_123", "127.0.0.1", "ua")

        old_row = SesionUsuario.objects.get(usuario=self.user, session_id=old_sid)
        self.assertEqual(old_row.cerrada_por, SesionUsuario.CierrePor.REVOCADA)
        self.assertIsNotNone(old_row.fch_fin)
        self.assertEqual(
            SesionUsuario.objects.filter(
                usuario=self.user, fch_fin__isnull=True
            ).count(),
            1,
        )

    # Guard unit tests
    def test_consume_reset_jti_second_use_is_rejected(self):
        payload = {"jti": "jti-guard-1"}

        consume_reset_jti(payload)

        with self.assertRaises(AuthServiceError) as ctx:
            consume_reset_jti(payload)
        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")

    def test_consume_reset_jti_without_jti_is_invalid(self):
        with self.assertRaises(AuthServiceError) as ctx:
            consume_reset_jti({})

        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")

    def test_ensure_user_can_reset_accepts_active_user(self):
        ensure_user_can_reset(self.user)
