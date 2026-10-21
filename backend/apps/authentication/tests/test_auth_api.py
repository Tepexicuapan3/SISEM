from http.cookies import SimpleCookie
from unittest.mock import patch

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, SesionUsuario, SyUsuario
from apps.authentication.services.errors import (
    AuthServiceError,
    PolicyStoreUnavailableError,
)
from apps.authentication.services.otp_service import store_code
from apps.authentication.services.token_service import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    RESET_COOKIE,
    create_reset_token,
    generate_csrf_token,
)
from apps.catalogos.models import Permisos, Roles
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class AuthApiTests(APITestCase):
    """KAN-92 critical contractual suite (TC001/TC003/TC006/TC017/TC021)."""

    def setUp(self):
        cache.clear()
        self.user = SyUsuario.objects.create(
            usuario="abelb",
            correo="abel@example.com",
            clave_hash=make_password("Abel_180903"),
            est_activo=True,
            cambiar_clave=True,
            terminos_acept=False,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Abel",
            paterno="Buendia",
            materno="Velazco",
        )
        self.role = Roles.objects.create(
            rol="MEDICO",
            desc_rol="Medico",
            landing_route="/expedientes",
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=self.role,
            is_primary=True,
        )
        self.perm = Permisos.objects.create(
            codigo="expedientes:read",
            descripcion="Leer expedientes",
        )
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm)

    def _login(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
            HTTP_X_REQUEST_ID="11111111-1111-1111-1111-111111111111",
        )
        self.client.cookies = response.cookies
        return response

    def test_login_sets_cookies(self):
        response = self._login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(ACCESS_COOKIE, response.cookies)
        self.assertIn(REFRESH_COOKIE, response.cookies)
        self.assertIn(CSRF_COOKIE, response.cookies)
        self.assertEqual(response.cookies[ACCESS_COOKIE]["samesite"], "Lax")
        self.assertEqual(response.cookies[ACCESS_COOKIE]["path"], "/")
        self.assertEqual(response.cookies[REFRESH_COOKIE]["samesite"], "Strict")
        self.assertIn("user", response.data)
        self.assertTrue(response.data["requiresOnboarding"])
        self.assertEqual(response.data["user"]["primaryRole"], "MEDICO")
        self.assertEqual(response.data["user"]["landingRoute"], "/expedientes")
        self.assertEqual(response.data["user"]["roles"], ["MEDICO"])
        self.assertEqual(response.data["user"]["permissions"], ["expedientes:read"])
        self.assertTrue(response.data["user"]["authRevision"])
        self.assertTrue(response.data["user"]["requiresOnboarding"])
        self.assertEqual(
            AuditoriaEvento.objects.filter(accion="LOGIN_SUCCESS").count(), 1
        )

    def test_login_sets_cookie_security_contract(self):
        """KAN-92/TC001: HttpOnly auth cookies + readable CSRF cookie."""
        response = self._login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[ACCESS_COOKIE]["httponly"], True)
        self.assertEqual(response.cookies[REFRESH_COOKIE]["httponly"], True)
        self.assertEqual(response.cookies[CSRF_COOKIE]["httponly"], "")

    def test_login_blocks_relogin_when_session_is_active(self):
        # Control de sesion unica (commit 57698a8): login usa block_if_active=True.
        self._login()

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "SESSION_ALREADY_ACTIVE")
        self.assertNotIn(ACCESS_COOKIE, response.cookies)

    def test_login_with_active_session_still_validates_credentials(self):
        self._login()

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "INVALID_CREDENTIALS")

    def test_login_blocks_second_browser_session_for_same_user(self):
        # Control de sesion unica (commit 57698a8): un segundo equipo es rechazado.
        first_login = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
        )
        self.assertEqual(first_login.status_code, status.HTTP_200_OK)

        second_client = self.client_class()
        second_login = second_client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
        )

        self.assertEqual(second_login.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second_login.data["code"], "SESSION_ALREADY_ACTIVE")
        self.assertNotIn(ACCESS_COOKIE, second_login.cookies)

    def test_login_invalid_password_has_request_id(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
            HTTP_X_REQUEST_ID="req-123",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "INVALID_CREDENTIALS")
        self.assertEqual(response.data["requestId"], "req-123")
        self.assertIn("timestamp", response.data)

    def test_login_invalid_password_preserves_request_id_in_response_header(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
            HTTP_X_REQUEST_ID="req-kan-51-preserve",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["X-Request-ID"], "req-kan-51-preserve")
        self.assertEqual(response.data["requestId"], "req-kan-51-preserve")

    def test_login_invalid_password_generates_request_id_when_header_is_missing(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
        )

        response_request_id = response.get("X-Request-ID")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(response_request_id)
        self.assertEqual(response.data["requestId"], response_request_id)

    def test_login_failed_audit_event_carries_request_id(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
            HTTP_X_REQUEST_ID="req-login-audit",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["requestId"], "req-login-audit")
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                accion="LOGIN_FAILED",
                resultado="FAIL",
                codigo_error="INVALID_CREDENTIALS",
                request_id="req-login-audit",
            ).exists()
        )

    def test_me_returns_user(self):
        self._login()

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "abelb")
        self.assertEqual(response.data["roles"], ["MEDICO"])
        self.assertEqual(response.data["permissions"], ["expedientes:read"])
        self.assertTrue(response.data["authRevision"])
        self.assertEqual(response["X-Auth-Revision"], response.data["authRevision"])

    def test_capabilities_returns_projection(self):
        self._login()

        response = self.client.get("/api/v1/auth/capabilities")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {
                "permissions",
                "effectivePermissions",
                "capabilities",
                "permissionDependenciesVersion",
                "strictCapabilityPrefixes",
                "authRevision",
            },
        )
        self.assertEqual(response.data["permissions"], ["expedientes:read"])
        self.assertIsInstance(response.data["effectivePermissions"], list)
        self.assertIsInstance(response.data["capabilities"], dict)
        self.assertEqual(response["X-Auth-Revision"], response.data["authRevision"])

    def test_capabilities_requires_auth(self):
        response = self.client.get(
            "/api/v1/auth/capabilities",
            HTTP_X_REQUEST_ID="req-capabilities-401",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")
        self.assertEqual(response.data["requestId"], "req-capabilities-401")
        self.assertEqual(response["X-Request-ID"], "req-capabilities-401")

    def test_capabilities_returns_403_for_inactive_user(self):
        self._login()
        self.user.est_activo = False
        self.user.save(update_fields=["est_activo"])

        response = self.client.get("/api/v1/auth/capabilities")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    @patch("apps.authentication.views.build_capabilities_response")
    def test_capabilities_returns_500_when_projection_fails(self, projection_mock):
        self._login()
        projection_mock.side_effect = RuntimeError("projection-broken")

        response = self.client.get(
            "/api/v1/auth/capabilities",
            HTTP_X_REQUEST_ID="req-capabilities-500",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(response.data["requestId"], "req-capabilities-500")
        self.assertEqual(response["X-Request-ID"], "req-capabilities-500")
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                accion="CAPABILITIES_READ",
                resultado="FAIL",
                codigo_error="INTERNAL_SERVER_ERROR",
            ).exists()
        )

    def test_verify_requires_auth(self):
        """KAN-92/TC017: verify returns 401 when no session exists."""
        response = self.client.get("/api/v1/auth/verify")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data, {"valid": False})

        self._login()
        response = self.client.get("/api/v1/auth/verify")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"valid": True})

    def test_refresh_rotates_tokens(self):
        login_response = self._login()

        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        refresh_token = login_response.cookies.get(REFRESH_COOKIE).value
        self.client.cookies[REFRESH_COOKIE] = refresh_token

        response = self.client.post(
            "/api/v1/auth/refresh",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(ACCESS_COOKIE, response.cookies)
        self.assertIn(CSRF_COOKIE, response.cookies)
        self.assertTrue(response.data["success"])

    def test_refresh_missing_cookie(self):
        response = self.client.post("/api/v1/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")

    def test_refresh_requires_csrf(self):
        login_response = self._login()

        refresh_token = login_response.cookies.get(REFRESH_COOKIE).value
        self.client.cookies[REFRESH_COOKIE] = refresh_token

        response = self.client.post("/api/v1/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_logout_requires_csrf(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

        response = self.client.post(
            "/api/v1/auth/logout",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_logout_invalidates_verify_session(self):
        """KAN-92/TC021: logout clears auth context for verify endpoint."""
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        verify_before = self.client.get("/api/v1/auth/verify")
        self.assertEqual(verify_before.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_before.data, {"valid": True})

        logout_response = self.client.post(
            "/api/v1/auth/logout",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        verify_after = self.client.get("/api/v1/auth/verify")
        self.assertEqual(verify_after.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(verify_after.data, {"valid": False})

    def test_complete_onboarding(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/complete-onboarding",
            {"newPassword": "Abel_180903", "termsAccepted": True},
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["requiresOnboarding"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.cambiar_clave)
        self.assertTrue(self.user.terminos_acept)

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                "OPTIONS": {"min_length": 12},
            }
        ]
    )
    def test_complete_onboarding_password_weak(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/complete-onboarding",
            {"newPassword": "corta", "termsAccepted": True},
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "PASSWORD_TOO_WEAK")

    def test_complete_onboarding_auth_error_is_audited_with_request_id(self):
        response = self.client.post(
            "/api/v1/auth/complete-onboarding",
            {"newPassword": "Abel_180903", "termsAccepted": True},
            format="json",
            HTTP_X_REQUEST_ID="req-onboarding-auth",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")
        self.assertEqual(response.data["requestId"], "req-onboarding-auth")
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                accion="ONBOARDING_FAILED",
                resultado="FAIL",
                codigo_error="TOKEN_INVALID",
                request_id="req-onboarding-auth",
            ).exists()
        )

    def test_request_reset_code(self):
        response = self.client.post(
            "/api/v1/auth/request-reset-code",
            {"email": "abel@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_request_reset_code_user_not_found(self):
        response = self.client.post(
            "/api/v1/auth/request-reset-code",
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "USER_NOT_FOUND")
        self.assertIn("timestamp", response.data)

    @patch(
        "apps.authentication.uses_case.request_reset_code_usecase.send_reset_code_email"
    )
    def test_request_reset_code_email_failure(self, send_mail_mock):
        send_mail_mock.return_value = False

        response = self.client.post(
            "/api/v1/auth/request-reset-code",
            {"email": "abel@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["code"], "INTERNAL_SERVER_ERROR")

    def test_verify_reset_code_sets_cookie(self):
        store_code("abel@example.com", "123456")

        response = self.client.post(
            "/api/v1/auth/verify-reset-code",
            {"email": "abel@example.com", "code": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"valid": True})
        self.assertIn(RESET_COOKIE, response.cookies)
        self.assertIn(CSRF_COOKIE, response.cookies)

    def test_verify_reset_code_invalid(self):
        store_code("abel@example.com", "123456")

        response = self.client.post(
            "/api/v1/auth/verify-reset-code",
            {"email": "abel@example.com", "code": "000000"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "INVALID_CODE")

    def test_verify_reset_code_rate_limit(self):
        store_code("abel@example.com", "123456")

        response = None
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/verify-reset-code",
                {"email": "abel@example.com", "code": "000000"},
                format="json",
            )

        response = self.client.post(
            "/api/v1/auth/verify-reset-code",
            {"email": "abel@example.com", "code": "000000"},
            format="json",
            HTTP_X_REQUEST_ID="req-verify-lock",
        )

        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)
        self.assertEqual(response.data["code"], "ACCOUNT_LOCKED")
        self.assertEqual(response.data["requestId"], "req-verify-lock")
        self.assertEqual(response["X-Request-ID"], "req-verify-lock")

    def test_verify_reset_code_expired(self):
        response = self.client.post(
            "/api/v1/auth/verify-reset-code",
            {"email": "abel@example.com", "code": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "CODE_EXPIRED")

    def test_reset_password(self):
        reset_token = create_reset_token(self.user)
        self.client.cookies[RESET_COOKIE] = reset_token

        csrf_token = generate_csrf_token()
        self.client.cookies[CSRF_COOKIE] = csrf_token

        response = self.client.post(
            "/api/v1/auth/reset-password",
            {"newPassword": "Nueva_Clave_123"},
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(ACCESS_COOKIE, response.cookies)
        self.assertTrue(response.data["requiresOnboarding"])

    def test_reset_password_token_is_single_use(self):
        # R5-S1: el mismo reset token no puede usarse dos veces.
        reset_token = create_reset_token(self.user)
        csrf_token = generate_csrf_token()

        def _post_reset(new_password):
            self.client.cookies[RESET_COOKIE] = reset_token
            self.client.cookies[CSRF_COOKIE] = csrf_token
            return self.client.post(
                "/api/v1/auth/reset-password",
                {"newPassword": new_password},
                format="json",
                HTTP_X_CSRF_TOKEN=csrf_token,
            )

        first = _post_reset("Nueva_Clave_123")
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = _post_reset("Otra_Clave_456")
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(second.data["code"], "TOKEN_INVALID")
        self.user.refresh_from_db()
        self.assertTrue(check_password("Nueva_Clave_123", self.user.clave_hash))

    def test_reset_password_inactive_user_returns_token_invalid(self):
        # R5-S2: no se revela el estado de la cuenta; la clave no cambia.
        reset_token = create_reset_token(self.user)
        self.user.est_activo = False
        self.user.save(update_fields=["est_activo"])
        self.client.cookies[RESET_COOKIE] = reset_token
        csrf_token = generate_csrf_token()
        self.client.cookies[CSRF_COOKIE] = csrf_token

        response = self.client.post(
            "/api/v1/auth/reset-password",
            {"newPassword": "Nueva_Clave_123"},
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")
        self.user.refresh_from_db()
        self.assertTrue(check_password("Abel_180903", self.user.clave_hash))

    def test_reset_password_fail_closed_when_jti_store_unavailable(self):
        # R5-S3: Redis caido al consumir el jti -> 503 y clave sin cambios.
        reset_token = create_reset_token(self.user)
        self.client.cookies[RESET_COOKIE] = reset_token
        csrf_token = generate_csrf_token()
        self.client.cookies[CSRF_COOKIE] = csrf_token

        with patch(
            "apps.authentication.services.reset_token_guard.reset_token_store.mark_consumed",
            side_effect=PolicyStoreUnavailableError("down"),
        ):
            response = self.client.post(
                "/api/v1/auth/reset-password",
                {"newPassword": "Nueva_Clave_123"},
                format="json",
                HTTP_X_CSRF_TOKEN=csrf_token,
            )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "SERVICE_UNAVAILABLE")
        self.user.refresh_from_db()
        self.assertTrue(check_password("Abel_180903", self.user.clave_hash))

    def test_reset_password_requires_csrf(self):
        reset_token = create_reset_token(self.user)
        self.client.cookies[RESET_COOKIE] = reset_token

        csrf_token = generate_csrf_token()
        self.client.cookies[CSRF_COOKIE] = csrf_token

        response = self.client.post(
            "/api/v1/auth/reset-password",
            {"newPassword": "Nueva_Clave_123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_reset_password_missing_token(self):
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {"newPassword": "Nueva_Clave_123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")

    def test_reset_password_missing_token_is_audited_with_request_id(self):
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {"newPassword": "Nueva_Clave_123"},
            format="json",
            HTTP_X_REQUEST_ID="req-reset-missing-token",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")
        self.assertEqual(response.data["requestId"], "req-reset-missing-token")
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                accion="PASSWORD_RESET_FAILED",
                resultado="FAIL",
                codigo_error="TOKEN_INVALID",
                request_id="req-reset-missing-token",
            ).exists()
        )

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                "OPTIONS": {"min_length": 12},
            }
        ]
    )
    def test_reset_password_password_weak(self):
        reset_token = create_reset_token(self.user)
        self.client.cookies[RESET_COOKIE] = reset_token

        csrf_token = generate_csrf_token()
        self.client.cookies[CSRF_COOKIE] = csrf_token

        response = self.client.post(
            "/api/v1/auth/reset-password",
            {"newPassword": "corta"},
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "PASSWORD_TOO_WEAK")

    def test_change_password_success(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
                "newPassword": "Nueva_Clave_123",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
            HTTP_X_REQUEST_ID="req-change-password-success",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["sessionRotated"])

        self.user.refresh_from_db()
        self.assertTrue(check_password("Nueva_Clave_123", self.user.clave_hash))
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                accion="PASSWORD_CHANGE_SUCCESS",
                resultado="SUCCESS",
                request_id="req-change-password-success",
            ).exists()
        )

    def test_change_password_rotates_session_and_invalidates_old_cookies(self):
        # R4-S1: cookies nuevas en la respuesta; el sid viejo deja de valer.
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value
        old_access = login_response.cookies[ACCESS_COOKIE].value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
                "newPassword": "Nueva_Clave_123",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["sessionRotated"])
        self.assertIn(ACCESS_COOKIE, response.cookies)
        self.assertIn(REFRESH_COOKIE, response.cookies)
        self.assertIn(CSRF_COOKIE, response.cookies)
        new_access = response.cookies[ACCESS_COOKIE].value
        self.assertNotEqual(new_access, old_access)

        # Request con el access viejo -> sesion reemplazada.
        self.client.cookies = SimpleCookie({ACCESS_COOKIE: old_access})
        old_response = self.client.get("/api/v1/auth/me")
        self.assertEqual(old_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(old_response.data["code"], "SESSION_EXPIRED")

        # Request con las cookies nuevas -> OK.
        self.client.cookies = SimpleCookie({ACCESS_COOKIE: new_access})
        new_response = self.client.get("/api/v1/auth/me")
        self.assertEqual(new_response.status_code, status.HTTP_200_OK)

        # Historial: una sola fila abierta, la anterior REVOCADA.
        self.assertEqual(
            SesionUsuario.objects.filter(
                usuario=self.user, fch_fin__isnull=True
            ).count(),
            1,
        )
        self.assertEqual(
            SesionUsuario.objects.filter(
                usuario=self.user, cerrada_por=SesionUsuario.CierrePor.REVOCADA
            ).count(),
            1,
        )

    def test_change_password_invalid_current_keeps_session_and_sets_no_cookies(self):
        # R4-S2: la sesion queda intacta y no se emiten cookies nuevas.
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "ClaveMala1",
                "newPassword": "Nueva_Clave_123",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(ACCESS_COOKIE, response.cookies)
        me_response = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)

    def test_change_password_returns_session_rotated_false_when_rotation_fails(self):
        # Redis caido al rotar: la clave ya cambio -> 200 sin cookies nuevas.
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        with patch("apps.authentication.views.rotate_user_session") as rotate_mock:
            rotate_mock.side_effect = AuthServiceError(
                "SERVICE_UNAVAILABLE", "Servicio temporalmente no disponible", 503
            )
            response = self.client.post(
                "/api/v1/auth/change-password",
                {
                    "currentPassword": "Abel_180903",
                    "newPassword": "Nueva_Clave_123",
                },
                format="json",
                HTTP_X_CSRF_TOKEN=csrf_token,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertFalse(response.data["sessionRotated"])
        self.assertNotIn(ACCESS_COOKIE, response.cookies)
        self.user.refresh_from_db()
        self.assertTrue(check_password("Nueva_Clave_123", self.user.clave_hash))
        self.assertTrue(
            AuditoriaEvento.objects.filter(
                accion="PASSWORD_CHANGE_SESSION_ROTATION_FAILED",
                resultado="FAIL",
            ).exists()
        )

    def test_change_password_requires_auth(self):
        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
                "newPassword": "Nueva_Clave_123",
            },
            format="json",
            HTTP_X_REQUEST_ID="req-change-password-auth",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")
        self.assertEqual(response.data["requestId"], "req-change-password-auth")

    def test_change_password_requires_csrf(self):
        self._login()

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
                "newPassword": "Nueva_Clave_123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_change_password_invalid_current_password(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "ClaveMala1",
                "newPassword": "Nueva_Clave_123",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
            HTTP_X_REQUEST_ID="req-change-password-invalid-current",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "INVALID_CREDENTIALS")
        self.assertEqual(
            response.data["requestId"], "req-change-password-invalid-current"
        )

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                "OPTIONS": {"min_length": 12},
            }
        ]
    )
    def test_change_password_password_weak(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
                "newPassword": "corta",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "PASSWORD_TOO_WEAK")

    def test_change_password_rejects_same_password(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
                "newPassword": "Abel_180903",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_change_password_missing_new_password_returns_validation_error(self):
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/auth/change-password",
            {
                "currentPassword": "Abel_180903",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_login_attempts_cleared_after_success(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        success = self._login()
        self.assertEqual(success.status_code, status.HTTP_200_OK)
        self.client.cookies.clear()

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_user_inactive(self):
        self.user.est_activo = False
        self.user.save(update_fields=["est_activo"])

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "USER_INACTIVE")

    def test_login_user_blocked(self):
        self.user.est_bloqueado = True
        self.user.save(update_fields=["est_bloqueado"])

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)
        self.assertEqual(response.data["code"], "ACCOUNT_LOCKED")

    def test_login_user_expired(self):
        self.user.fch_baja = timezone.now()
        self.user.save(update_fields=["fch_baja"])

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "Abel_180903"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "ACCOUNT_EXPIRED")

    def test_login_user_not_found(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "missing", "password": "Abel_180903"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "INVALID_CREDENTIALS")
        self.assertEqual(response.data["message"], "Usuario o contraseña incorrectos")
        self.assertIn("timestamp", response.data)

    def test_login_nonexistent_user_and_wrong_password_share_same_error_contract(self):
        missing_user_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "missing", "password": "Abel_180903"},
            format="json",
        )

        wrong_password_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
        )

        self.assertEqual(
            missing_user_response.status_code,
            wrong_password_response.status_code,
        )
        self.assertEqual(
            missing_user_response.data["code"],
            wrong_password_response.data["code"],
        )
        self.assertEqual(
            missing_user_response.data["message"],
            wrong_password_response.data["message"],
        )

    def test_login_invalid_password(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "INVALID_CREDENTIALS")

    def test_login_rate_limit(self):
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/login",
                {"username": "abelb", "password": "ClaveMala1"},
                format="json",
            )

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
            HTTP_X_REQUEST_ID="req-login-lock",
        )

        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)
        self.assertEqual(response.data["code"], "ACCOUNT_LOCKED")
        self.assertEqual(response.data["requestId"], "req-login-lock")
        self.assertEqual(response["X-Request-ID"], "req-login-lock")

    def test_login_ip_throttle_returns_429(self):
        response = None
        for index in range(1, 22):
            username = f"ip_user_{index}"
            SyUsuario.objects.create(
                usuario=username,
                correo=f"{username}@example.com",
                clave_hash=make_password("Abel_180903"),
                est_activo=True,
                cambiar_clave=True,
                terminos_acept=False,
            )

            response = self.client.post(
                "/api/v1/auth/login",
                {"username": username, "password": "ClaveMala1"},
                format="json",
                REMOTE_ADDR="198.51.100.23",
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "RATE_LIMIT_EXCEEDED")

    @patch(
        "apps.authentication.uses_case.request_reset_code_usecase.send_reset_code_email"
    )
    def test_request_reset_code_account_limit_is_three_per_fifteen_minutes(
        self, send_mail_mock
    ):
        send_mail_mock.return_value = True

        response = None
        for _ in range(4):
            response = self.client.post(
                "/api/v1/auth/request-reset-code",
                {"email": "abel@example.com"},
                format="json",
                HTTP_X_REQUEST_ID="req-reset-account-limit",
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "RATE_LIMIT_EXCEEDED")
        self.assertEqual(response.data["requestId"], "req-reset-account-limit")
        self.assertEqual(response["X-Request-ID"], "req-reset-account-limit")

    @patch(
        "apps.authentication.uses_case.request_reset_code_usecase.send_reset_code_email"
    )
    def test_request_reset_code_ip_limit_is_ten_per_fifteen_minutes(
        self, send_mail_mock
    ):
        send_mail_mock.return_value = True

        for index in range(1, 12):
            email = f"ip-limit-{index}@example.com"
            SyUsuario.objects.create(
                usuario=f"ip_limit_{index}",
                correo=email,
                clave_hash=make_password("Abel_180903"),
                est_activo=True,
                cambiar_clave=True,
                terminos_acept=False,
            )

            response = self.client.post(
                "/api/v1/auth/request-reset-code",
                {"email": email},
                format="json",
                REMOTE_ADDR="203.0.113.77",
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "RATE_LIMIT_EXCEEDED")

    @patch("apps.authentication.uses_case.login_usecase.policy_service.check_login")
    def test_login_fail_closed_when_policy_store_unavailable(self, check_login_mock):
        check_login_mock.side_effect = AuthServiceError(
            "SERVICE_UNAVAILABLE",
            "Servicio temporalmente no disponible",
            503,
        )

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
            HTTP_X_REQUEST_ID="req-login-503",
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "SERVICE_UNAVAILABLE")
        self.assertEqual(response.data["requestId"], "req-login-503")
        self.assertEqual(response["X-Request-ID"], "req-login-503")

    @patch(
        "apps.authentication.uses_case.request_reset_code_usecase.policy_service.check_reset_request"
    )
    def test_request_reset_fail_closed_when_policy_store_unavailable(
        self, check_reset_mock
    ):
        check_reset_mock.side_effect = AuthServiceError(
            "SERVICE_UNAVAILABLE",
            "Servicio temporalmente no disponible",
            503,
        )

        response = self.client.post(
            "/api/v1/auth/request-reset-code",
            {"email": "abel@example.com"},
            format="json",
            HTTP_X_REQUEST_ID="req-reset-503",
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "SERVICE_UNAVAILABLE")
        self.assertEqual(response.data["requestId"], "req-reset-503")
        self.assertEqual(response["X-Request-ID"], "req-reset-503")

    @patch(
        "apps.authentication.uses_case.verify_reset_code_usecase.policy_service.check_verify_code"
    )
    def test_verify_reset_fail_closed_when_policy_store_unavailable(
        self, check_verify_mock
    ):
        check_verify_mock.side_effect = AuthServiceError(
            "SERVICE_UNAVAILABLE",
            "Servicio temporalmente no disponible",
            503,
        )

        response = self.client.post(
            "/api/v1/auth/verify-reset-code",
            {"email": "abel@example.com", "code": "123456"},
            format="json",
            HTTP_X_REQUEST_ID="req-verify-503",
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "SERVICE_UNAVAILABLE")
        self.assertEqual(response.data["requestId"], "req-verify-503")
        self.assertEqual(response["X-Request-ID"], "req-verify-503")

    def test_policy_deny_is_audited_with_policy_metadata(self):
        for _ in range(5):
            self.client.post(
                "/api/v1/auth/login",
                {"username": "abelb", "password": "ClaveMala1"},
                format="json",
                HTTP_X_REQUEST_ID="req-policy-audit",
            )

        self.client.post(
            "/api/v1/auth/login",
            {"username": "abelb", "password": "ClaveMala1"},
            format="json",
            HTTP_X_REQUEST_ID="req-policy-audit",
        )

        deny_event = AuditoriaEvento.objects.filter(
            accion="POLICY_ENFORCEMENT_DENY"
        ).latest("fch_evento")
        self.assertEqual(deny_event.request_id, "req-policy-audit")
        self.assertEqual(deny_event.meta.get("policyKey"), "login.account.lock")
        self.assertEqual(deny_event.meta.get("threshold"), 5)
        self.assertEqual(deny_event.meta.get("window"), "15m")
        self.assertIn("counterValue", deny_event.meta)
        self.assertIn("lockTtl", deny_event.meta)
