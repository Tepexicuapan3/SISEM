"""El backend ENFORCEA el onboarding (cambiar_clave / terminos_acept).

Antes solo lo imponia el guard del frontend: un usuario con clave temporal
podia llamar la API directo. Ahora authenticate_request responde 403
ONBOARDING_REQUIRED fuera de una allowlist exacta de endpoints /auth/*.
"""

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.session_service import ONBOARDING_ALLOWED_PATHS
from apps.authentication.services.token_service import CSRF_COOKIE

PASSWORD = "Onboard_123456"
REQUIRED = "ONBOARDING_REQUIRED"
PROTECTED_ADMIN = "/api/v1/users"
PROTECTED_CATALOG = "/api/v1/religions/"
PROTECTED_COOKIE_VIEW = "/api/v1/almacen/unidades-medida/"


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class OnboardingEnforcementTests(APITestCase):
    def setUp(self):
        cache.clear()

    def _login(self, *, cambiar_clave, terminos_acept, username="onb_user"):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password(PASSWORD),
            est_activo=True,
            cambiar_clave=cambiar_clave,
            terminos_acept=terminos_acept,
        )
        DetUsuario.objects.create(id_usuario=user, nombre="O", paterno="B", materno="")
        PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": username, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies
        self.csrf = response.cookies.get(CSRF_COOKIE).value
        return user

    def _assert_blocked(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, path)
        self.assertEqual(response.data["code"], REQUIRED, path)
        self.assertIn("contraseña temporal", response.data["message"])

    def test_cambiar_clave_blocks_admin_catalog_and_cookie_views(self):
        self._login(cambiar_clave=True, terminos_acept=True)
        for path in (PROTECTED_ADMIN, PROTECTED_CATALOG, PROTECTED_COOKIE_VIEW):
            self._assert_blocked(path)

    def test_terminos_pendientes_also_block(self):
        self._login(cambiar_clave=False, terminos_acept=False)
        for path in (PROTECTED_ADMIN, PROTECTED_CATALOG, PROTECTED_COOKIE_VIEW):
            self._assert_blocked(path)

    def test_allowlisted_endpoints_still_work(self):
        self._login(cambiar_clave=True, terminos_acept=False)
        for path in ("/api/v1/auth/me", "/api/v1/auth/verify"):
            self.assertEqual(self.client.get(path).status_code, status.HTTP_200_OK, path)
        self.assertEqual(
            self.client.get("/api/v1/auth/capabilities").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/refresh", HTTP_X_CSRF_TOKEN=self.csrf
            ).status_code,
            status.HTTP_200_OK,
        )

    def test_logout_is_allowed(self):
        self._login(cambiar_clave=True, terminos_acept=False)
        response = self.client.post("/api/v1/auth/logout", HTTP_X_CSRF_TOKEN=self.csrf)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_allowlist_is_exact_and_narrow(self):
        self.assertEqual(
            ONBOARDING_ALLOWED_PATHS,
            {
                "/api/v1/auth/me",
                "/api/v1/auth/capabilities",
                "/api/v1/auth/verify",
                "/api/v1/auth/refresh",
                "/api/v1/auth/logout",
                "/api/v1/auth/complete-onboarding",
                "/api/v1/auth/change-password",
            },
        )
        self._login(cambiar_clave=True, terminos_acept=False)
        self._assert_blocked("/api/v1/auth/ops/sessions")

    def test_access_works_after_complete_onboarding(self):
        self._login(cambiar_clave=True, terminos_acept=False)
        self._assert_blocked(PROTECTED_COOKIE_VIEW)

        response = self.client.post(
            "/api/v1/auth/complete-onboarding",
            {"newPassword": PASSWORD, "termsAccepted": True},
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

        after = self.client.get(PROTECTED_COOKIE_VIEW)
        self.assertEqual(after.status_code, status.HTTP_200_OK)
        admin_after = self.client.get(PROTECTED_ADMIN)
        self.assertNotEqual(admin_after.data.get("code"), REQUIRED)

    def test_user_without_pending_onboarding_is_not_blocked(self):
        self._login(cambiar_clave=False, terminos_acept=True)
        self.assertEqual(
            self.client.get(PROTECTED_COOKIE_VIEW).status_code, status.HTTP_200_OK
        )
