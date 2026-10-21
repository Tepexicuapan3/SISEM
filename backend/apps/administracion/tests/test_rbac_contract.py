from django.contrib.auth.hashers import make_password
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import Permisos, Roles


class RbacContractTests(APITestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="adminrbac",
            correo="admin.rbac@example.com",
            clave_hash=make_password("Admin_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Admin",
            paterno="RBAC",
            materno="",
        )

        self.role = Roles.objects.create(
            rol="ADMIN_RBAC",
            desc_rol="Administrador de pruebas",
            landing_route="/admin/roles",
            is_admin=True,
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=self.role,
            is_primary=True,
        )

        self.permission = Permisos.objects.create(
            codigo="admin:gestion:permisos:read",
            descripcion="Leer permisos",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.permission)

        # Redis (sesion unica) no se limpia entre tests como la DB -- un
        # user_id reciclado puede arrastrar una sesion "activa" de una
        # corrida anterior y el login choca con SESSION_ALREADY_ACTIVE (409).
        PolicyStore().clear_active_session(self.user.id_usuario)
        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "adminrbac", "password": "Admin_123456"},
            format="json",
        )
        assert login_response.status_code == status.HTTP_200_OK
        self.client.cookies = login_response.cookies
        self.csrf_token = login_response.cookies.get(CSRF_COOKIE).value

    def test_roles_list_contract(self):
        response = self.client.get("/api/v1/roles")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("page", response.data)
        self.assertIn("pageSize", response.data)
        self.assertIn("total", response.data)
        self.assertIn("totalPages", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

        item = response.data["items"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("description", item)
        self.assertIn("isActive", item)
        self.assertIn("isSystem", item)
        self.assertIn("landingRoute", item)
        self.assertIn("permissionsCount", item)
        self.assertIn("usersCount", item)

    def test_create_role_contract(self):
        response = self.client.post(
            "/api/v1/roles",
            {
                "name": "SUPERVISOR_RBAC",
                "description": "Rol de supervisor",
                "landingRoute": "/admin/supervisor",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "SUPERVISOR_RBAC")

    def test_permissions_catalog_contract(self):
        response = self.client.get("/api/v1/permissions")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("total", response.data)
        self.assertGreaterEqual(response.data["total"], 1)
        self.assertGreaterEqual(len(response.data["items"]), 1)

        item = response.data["items"][0]
        self.assertIn("id", item)
        self.assertIn("code", item)
        self.assertIn("description", item)
        self.assertIn("isSystem", item)
        self.assertIn("dependsOn", item)

    @override_settings(RBAC_READ_S1_ENABLED=False)
    def test_permissions_catalog_depends_on_parity_legacy_vs_s1(self):
        Permisos.objects.create(
            codigo="admin:gestion:usuarios:update",
            descripcion="Actualizar usuarios",
            is_active=True,
        )
        Permisos.objects.create(
            codigo="admin:gestion:usuarios:read",
            descripcion="Leer usuarios",
            is_active=True,
        )

        legacy = self.client.get("/api/v1/permissions")
        with self.settings(RBAC_READ_S1_ENABLED=True):
            s1 = self.client.get("/api/v1/permissions")

        self.assertEqual(legacy.status_code, status.HTTP_200_OK)
        self.assertEqual(s1.status_code, status.HTTP_200_OK)
        expected_keys = {"id", "code", "description", "isSystem", "dependsOn"}
        for response in (legacy, s1):
            for item in response.data["items"]:
                self.assertEqual(set(item.keys()), expected_keys)

        for response in (legacy, s1):
            by_code = {item["code"]: item for item in response.data["items"]}
            self.assertEqual(by_code["admin:gestion:usuarios:read"]["dependsOn"], [])
            update_deps = by_code["admin:gestion:usuarios:update"]["dependsOn"]
            self.assertIn("admin:gestion:roles:read", update_deps)
            self.assertIn("admin:gestion:permisos:read", update_deps)
            self.assertIn("admin:gestion:usuarios:read", update_deps)

        legacy_deps = {i["code"]: i["dependsOn"] for i in legacy.data["items"]}
        s1_deps = {i["code"]: i["dependsOn"] for i in s1.data["items"]}
        self.assertEqual(legacy_deps, s1_deps)

    def test_users_list_contract(self):
        response = self.client.get("/api/v1/users")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

        user_item = response.data["items"][0]
        self.assertIn("id", user_item)
        self.assertIn("username", user_item)
        self.assertIn("fullname", user_item)
        self.assertIn("email", user_item)
        self.assertIn("clinic", user_item)
        self.assertIn("primaryRole", user_item)
        self.assertIn("isActive", user_item)


class RbacReadS1ParityTests(APITestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="adminrbac_s1",
            correo="admin.rbac.s1@example.com",
            clave_hash=make_password("Admin_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Admin",
            paterno="RBAC",
            materno="S1",
        )

        self.role = Roles.objects.create(
            rol="ADMIN_RBAC_S1",
            desc_rol="Administrador de pruebas S1",
            landing_route="/admin/roles",
            is_admin=True,
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=self.role,
            is_primary=True,
        )

        permission = Permisos.objects.create(
            codigo="admin:gestion:permisos:read",
            descripcion="Leer permisos",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=permission)

        # Redis (sesion unica) no se limpia entre tests como la DB -- un
        # user_id reciclado puede arrastrar una sesion "activa" de una
        # corrida anterior y el login choca con SESSION_ALREADY_ACTIVE (409).
        PolicyStore().clear_active_session(self.user.id_usuario)
        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "adminrbac_s1", "password": "Admin_123456"},
            format="json",
        )
        assert login_response.status_code == status.HTTP_200_OK
        self.client.cookies = login_response.cookies

        self.target_role = Roles.objects.create(
            rol="RBAC_S1_TARGET",
            desc_rol="Rol target S1",
            landing_route="/target",
            is_active=True,
        )

    @override_settings(RBAC_READ_S1_ENABLED=False)
    def test_roles_contract_parity_legacy_vs_s1(self):
        legacy = self.client.get("/api/v1/roles")
        self.assertEqual(legacy.status_code, status.HTTP_200_OK)

        with self.settings(RBAC_READ_S1_ENABLED=True):
            s1 = self.client.get("/api/v1/roles")

        self.assertEqual(s1.status_code, legacy.status_code)
        self.assertEqual(set(s1.data.keys()), set(legacy.data.keys()))
        self.assertEqual(
            set(s1.data["items"][0].keys()), set(legacy.data["items"][0].keys())
        )

    @override_settings(RBAC_READ_S1_ENABLED=False)
    def test_role_detail_contract_parity_legacy_vs_s1(self):
        legacy = self.client.get(f"/api/v1/roles/{self.target_role.id_rol}")
        self.assertEqual(legacy.status_code, status.HTTP_200_OK)

        with self.settings(RBAC_READ_S1_ENABLED=True):
            s1 = self.client.get(f"/api/v1/roles/{self.target_role.id_rol}")

        self.assertEqual(s1.status_code, legacy.status_code)
        self.assertEqual(set(s1.data.keys()), set(legacy.data.keys()))
        self.assertEqual(set(s1.data["role"].keys()), set(legacy.data["role"].keys()))

    @override_settings(RBAC_READ_S1_ENABLED=True)
    def test_permissions_catalog_records_s1_source(self):
        response = self.client.get("/api/v1/permissions")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(accion="RBAC_PERMISSION_LIST").latest(
            "id_evento"
        )
        self.assertEqual(event.meta.get("source"), "s1")
