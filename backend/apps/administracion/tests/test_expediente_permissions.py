"""
Regresión de seguridad: ExpedienteView, ActualizarExpedienteView y
BuscarPorNombreView exponian datos de expedientes medicos a CUALQUIER
usuario autenticado, sin verificar el permiso RBAC
``admin:gestion:expedientes:read`` (unico permiso que el catalogo define
para este modulo, ver nav-config.ts / navigation_seed.py).

Estos tests fijan el contrato correcto:
  - sin sesion -> 401
  - con sesion pero SIN el permiso -> 403
  - con sesion Y el permiso (o wildcard "*") -> 200
"""

from unittest import mock

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import Permisos, Roles

PERMISO_EXPEDIENTES = "admin:gestion:expedientes:read"
PERMISO_ACTUALIZAR = "admin:gestion:expedientes:update"


class ExpedientePermissionsApiTests(APITestCase):
    def setUp(self):
        # Rol/usuario CON el permiso correcto.
        self.perm_expedientes = Permisos.objects.create(
            codigo=PERMISO_EXPEDIENTES,
            descripcion="Ver expedientes administrativos",
            is_active=True,
        )
        self.role_con_permiso = Roles.objects.create(
            rol="ROL_CON_EXPEDIENTES",
            desc_rol="Rol con acceso a expedientes",
            landing_route="/admin/expedientes",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=self.role_con_permiso, id_permiso=self.perm_expedientes)
        # Actualizar exige su propio permiso (change auditoria-sync-expedientes);
        # el caso "solo lectura" esta en test_sync_expediente_auditoria.
        # La migracion administracion 0015 ya lo da de alta.
        self.perm_actualizar, _ = Permisos.objects.get_or_create(
            codigo=PERMISO_ACTUALIZAR,
            defaults={"descripcion": "Actualizar expedientes desde SERMED", "is_active": True},
        )
        RelRolPermiso.objects.create(id_rol=self.role_con_permiso, id_permiso=self.perm_actualizar)

        self.user_con_permiso = SyUsuario.objects.create(
            usuario="user_con_expedientes",
            correo="con.permiso@example.com",
            clave_hash=make_password("Password_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user_con_permiso,
            nombre="Con",
            paterno="Permiso",
            materno="",
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user_con_permiso,
            id_rol=self.role_con_permiso,
            is_primary=True,
        )

        # Rol/usuario autenticado pero SIN el permiso de expedientes.
        self.role_sin_permiso = Roles.objects.create(
            rol="ROL_SIN_EXPEDIENTES",
            desc_rol="Rol sin acceso a expedientes",
            landing_route="/dashboard",
            is_active=True,
        )
        otro_permiso = Permisos.objects.create(
            codigo="admin:gestion:usuarios:read",
            descripcion="Ver usuarios",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=self.role_sin_permiso, id_permiso=otro_permiso)

        self.user_sin_permiso = SyUsuario.objects.create(
            usuario="user_sin_expedientes",
            correo="sin.permiso@example.com",
            clave_hash=make_password("Password_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user_sin_permiso,
            nombre="Sin",
            paterno="Permiso",
            materno="",
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user_sin_permiso,
            id_rol=self.role_sin_permiso,
            is_primary=True,
        )

    def _login_as(self, username, password="Password_123456"):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": username, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies
        return response.cookies.get(CSRF_COOKIE).value

    # ── ExpedienteView (GET /api/v1/expedientes/) ──────────────────────

    def test_get_expediente_sin_sesion_devuelve_401(self):
        response = self.client.get("/api/v1/expedientes/?id_empleado=40041")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_expediente_autenticado_sin_permiso_devuelve_403(self):
        self._login_as("user_sin_expedientes")

        response = self.client.get("/api/v1/expedientes/?id_empleado=40041")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_get_expediente_con_permiso_devuelve_200(self):
        self._login_as("user_con_expedientes")

        with mock.patch(
            "apps.administracion.views.expediente_view.buscar_expediente",
            return_value={"empleados": [{"NO_EXP": "40041"}], "familiares": []},
        ):
            response = self.client.get("/api/v1/expedientes/?id_empleado=40041")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["empleados"][0]["NO_EXP"], "40041")

    # ── BuscarPorNombreView (GET /api/v1/expedientes/buscar-nombre/) ───

    def test_buscar_por_nombre_sin_sesion_devuelve_401(self):
        response = self.client.get("/api/v1/expedientes/buscar-nombre/?nombre=Perez")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_buscar_por_nombre_autenticado_sin_permiso_devuelve_403(self):
        self._login_as("user_sin_expedientes")

        response = self.client.get("/api/v1/expedientes/buscar-nombre/?nombre=Perez")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_buscar_por_nombre_con_permiso_devuelve_200(self):
        self._login_as("user_con_expedientes")

        with mock.patch(
            "apps.administracion.views.expediente_view.buscar_por_nombre",
            return_value=[{"NO_EXP": "40041"}],
        ):
            response = self.client.get("/api/v1/expedientes/buscar-nombre/?nombre=Perez")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["NO_EXP"], "40041")

    # ── ActualizarExpedienteView (POST /api/v1/expedientes/actualizar/) ─

    def test_actualizar_expediente_sin_sesion_devuelve_401(self):
        response = self.client.post(
            "/api/v1/expedientes/actualizar/",
            {"expediente": "40041"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_actualizar_expediente_autenticado_sin_permiso_devuelve_403(self):
        csrf_token = self._login_as("user_sin_expedientes")

        response = self.client.post(
            "/api/v1/expedientes/actualizar/",
            {"expediente": "40041"},
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_actualizar_expediente_con_permiso_sin_csrf_devuelve_403(self):
        self._login_as("user_con_expedientes")

        response = self.client.post(
            "/api/v1/expedientes/actualizar/",
            {"expediente": "40041"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_actualizar_expediente_con_permiso_y_csrf_devuelve_200(self):
        csrf_token = self._login_as("user_con_expedientes")

        with mock.patch(
            "apps.administracion.views.expediente_view.actualizar_expediente",
            return_value={
                "estado": "OK",
                "id_sync": 1,
                "tablas": {"cat_empleados": {"actualizados": 1}},
                "errores": [],
            },
        ):
            response = self.client.post(
                "/api/v1/expedientes/actualizar/",
                {"expediente": "40041"},
                format="json",
                HTTP_X_CSRF_TOKEN=csrf_token,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["errores"], [])
