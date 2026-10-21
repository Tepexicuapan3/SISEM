"""Cobertura para POST /api/v1/medicos -- antes de este test la app
`medicos` no tenia NINGUNA prueba, y el gate de tipo_personal en
medico_views.py:193 llevaba tiempo roto sin que nada lo detectara (ver
memoria del proyecto: bugfix DetUsuario.tipo_personal). Estos tests fijan
el comportamiento correcto: el gate debe basarse en la FK real
(id_tipo_personal), no en texto libre."""

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import CatTipoPersonal, Permisos, Roles
from apps.medicos.models import CatMedico

MEDICOS_URL = "/api/v1/medicos"


class MedicoCreateApiTests(APITestCase):
    """No usa el flujo HTTP de /api/v1/auth/login: ese endpoint valida
    "sesion ya activa" contra Redis con block_if_active=True, y el estado
    de Redis no se limpia entre tests (a diferencia de la DB, que Django
    revierte por transaccion) -- eso causa 409 intermitentes entre suites
    que reusan el mismo username. Se llama a start_session(...) directo
    (con block_if_active=False, el default) para registrar la sesion en
    Redis sin ese chequeo."""

    def setUp(self):
        self.tipo_medico, _ = CatTipoPersonal.objects.get_or_create(
            name="Médico", defaults={"is_active": True}
        )
        self.tipo_admin, _ = CatTipoPersonal.objects.get_or_create(
            name="Administrativo", defaults={"is_active": True}
        )

        self.role, _ = Roles.objects.get_or_create(
            rol="ADMIN_MEDICOS_TEST",
            defaults={"desc_rol": "Admin gestion medicos (test)", "landing_route": "/admin"},
        )
        permiso, _ = Permisos.objects.get_or_create(
            codigo="admin:gestion:medicos:create",
            defaults={"descripcion": "Crear medicos", "is_active": True},
        )
        RelRolPermiso.objects.get_or_create(id_rol=self.role, id_permiso=permiso)

        self.actor = self._create_user("admin_actor", tipo_personal=self.tipo_admin)
        self.auth_headers = self._auth_headers(self.actor)

    def _create_user(self, username, tipo_personal):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user,
            nombre=username,
            paterno="Test",
            materno="User",
            id_tipo_personal=tipo_personal,
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=self.role, is_primary=True)
        return user

    def _auth_headers(self, user):
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def test_post_medico_happy_path_when_tipo_personal_is_medico(self):
        medico_user = self._create_user("medico_nuevo", tipo_personal=self.tipo_medico)

        response = self.client.post(
            MEDICOS_URL,
            {"usuarioId": medico_user.id_usuario},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CatMedico.objects.filter(id_usuario=medico_user).exists())

    def test_post_medico_rejects_when_tipo_personal_is_not_medico(self):
        non_medico_user = self._create_user("no_medico", tipo_personal=self.tipo_admin)

        response = self.client.post(
            MEDICOS_URL,
            {"usuarioId": non_medico_user.id_usuario},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "TIPO_PERSONAL_INVALIDO")
        self.assertFalse(CatMedico.objects.filter(id_usuario=non_medico_user).exists())

    def test_post_medico_rejects_when_no_tipo_personal_assigned(self):
        sin_tipo_user = self._create_user("sin_tipo", tipo_personal=None)

        response = self.client.post(
            MEDICOS_URL,
            {"usuarioId": sin_tipo_user.id_usuario},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "TIPO_PERSONAL_INVALIDO")

    def test_post_medico_rejects_when_profile_already_exists(self):
        medico_user = self._create_user("medico_duplicado", tipo_personal=self.tipo_medico)
        CatMedico.objects.create(id_usuario=medico_user)

        response = self.client.post(
            MEDICOS_URL,
            {"usuarioId": medico_user.id_usuario},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "MEDICO_EXISTS")

    def test_post_medico_requires_usuario_id(self):
        response = self.client.post(
            MEDICOS_URL,
            {},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_post_medico_without_usuario_id_ignores_nombre_display(self):
        # No existe el camino de alta sin usuario (ni con nombreDisplay).
        response = self.client.post(
            MEDICOS_URL,
            {"nombreDisplay": "Dr. Sin Usuario"},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(CatMedico.objects.count(), 0)

    def test_post_medico_unknown_usuario_returns_404(self):
        response = self.client.post(
            MEDICOS_URL, {"usuarioId": 999999}, format="json", **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_allow_sin_usuario_flag_no_longer_exists(self):
        # R7/S7.4
        from django.conf import settings

        self.assertFalse(hasattr(settings, "MEDICOS_ALLOW_SIN_USUARIO"))


class MedicoSearchApiTests(APITestCase):
    """GET /api/v1/medicos?search=... no tenia ninguna prueba. Cubre el
    filtro multi-palabra compartido con /api/v1/users (_apply_user_search_filter
    en rbac_views.py): cada palabra del texto buscado puede matchear en
    `usuario` o en `nombre_completo`, sin necesidad de que ambas esten en el
    mismo campo."""

    def setUp(self):
        self.tipo_medico, _ = CatTipoPersonal.objects.get_or_create(
            name="Médico", defaults={"is_active": True}
        )

        self.read_role, _ = Roles.objects.get_or_create(
            rol="LECTOR_MEDICOS_TEST",
            defaults={"desc_rol": "Lectura medicos (test)", "landing_route": "/admin"},
        )
        permiso, _ = Permisos.objects.get_or_create(
            codigo="admin:gestion:medicos:read",
            defaults={"descripcion": "Leer medicos", "is_active": True},
        )
        RelRolPermiso.objects.get_or_create(id_rol=self.read_role, id_permiso=permiso)

        self.actor = self._create_reader("lector_medicos")
        self.auth_headers = self._auth_headers(self.actor)

        self.medico_user = SyUsuario.objects.create(
            usuario="dra_gonzalez",
            correo="dra.gonzalez@example.com",
            clave_hash=make_password("x"),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.medico_user,
            nombre="Ana",
            paterno="Gonzalez",
            materno="Ruiz",
            id_tipo_personal=self.tipo_medico,
        )
        CatMedico.objects.create(id_usuario=self.medico_user)

    def _create_reader(self, username):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=self.read_role, is_primary=True)
        return user

    def _auth_headers(self, user):
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def test_search_matches_single_field(self):
        response = self.client.get(MEDICOS_URL, {"search": "Gonzalez"}, **self.auth_headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data["items"]}
        self.assertIn("dra_gonzalez", usernames)

    def test_search_matches_across_username_and_full_name(self):
        # "dra_gonzalez" solo esta en `usuario` y "Ana" solo esta en
        # `nombre_completo` -- ningun campo individual contiene la frase
        # completa "dra_gonzalez Ana".
        response = self.client.get(
            MEDICOS_URL, {"search": "dra_gonzalez Ana"}, **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data["items"]}
        self.assertIn("dra_gonzalez", usernames)

    def test_search_without_match_returns_empty(self):
        response = self.client.get(
            MEDICOS_URL, {"search": "nombre_que_no_existe"}, **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data["items"]}
        self.assertNotIn("dra_gonzalez", usernames)
