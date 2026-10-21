from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import CatPermiso, CatRol, Permisos, Roles


class RbacRolesPermissionsApiTests(APITestCase):
    def setUp(self):
        self.admin = SyUsuario.objects.create(
            usuario="admin_roles",
            correo="admin.roles@example.com",
            clave_hash=make_password("Admin_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.admin,
            nombre="Admin",
            paterno="Roles",
            materno="",
        )

        self.admin_role = Roles.objects.create(
            rol="ADMIN_TEST_ROLES",
            desc_rol="Administrador de pruebas",
            landing_route="/admin",
            is_admin=True,
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.admin,
            id_rol=self.admin_role,
            is_primary=True,
        )

        self.target_role = Roles.objects.create(
            rol="MEDICO_TEST_ROLES",
            desc_rol="Rol medico",
            landing_route="/expedientes",
            is_active=True,
        )
        self.system_role = Roles.objects.create(
            rol="SYSTEM_LOCKED_ROLE",
            desc_rol="Rol de sistema",
            landing_route="/system",
            es_sistema=True,
            is_active=True,
        )

        self.perm_read = Permisos.objects.create(
            codigo="pacientes:read",
            descripcion="Leer pacientes",
            is_active=True,
        )
        self.perm_update = Permisos.objects.create(
            codigo="pacientes:update",
            descripcion="Actualizar pacientes",
            is_active=True,
        )
        self.perm_extra = Permisos.objects.create(
            codigo="agenda:read",
            descripcion="Leer agenda",
            is_active=True,
        )

        # Redis (sesion unica) no se limpia entre tests como la DB -- un
        # user_id reciclado puede arrastrar una sesion "activa" de una
        # corrida anterior y el login choca con SESSION_ALREADY_ACTIVE (409).
        PolicyStore().clear_active_session(self.admin.id_usuario)
        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "admin_roles", "password": "Admin_123456"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.client.cookies = login_response.cookies
        self.csrf_token = login_response.cookies.get(CSRF_COOKIE).value

    def _login_as(self, username, password):
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
        self.csrf_token = response.cookies.get(CSRF_COOKIE).value

    def test_roles_list_invalid_sort_by_returns_validation_error(self):
        response = self.client.get("/api/v1/roles?sortBy=invalido")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("details", response.data)

    def test_roles_list_search_filters_and_sorting(self):
        response = self.client.get(
            "/api/v1/roles?search=MEDICO&isActive=true&isSystem=false&sortBy=name&sortOrder=desc"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)

    def test_roles_list_invalid_is_system_returns_validation_error(self):
        response = self.client.get("/api/v1/roles?isSystem=talvez")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_roles_list_invalid_sort_order_returns_validation_error(self):
        response = self.client.get("/api/v1/roles?sortOrder=up")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_roles_list_invalid_is_active_returns_validation_error(self):
        response = self.client.get("/api/v1/roles?isActive=maybe")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_roles_list_invalid_pagination_format_returns_invalid_format(self):
        response = self.client.get("/api/v1/roles?page=uno&pageSize=veinte")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "INVALID_FORMAT")

    def test_role_detail_not_found(self):
        response = self.client.get("/api/v1/roles/999999")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_role_detail_success(self):
        response = self.client.get(f"/api/v1/roles/{self.target_role.id_rol}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("role", response.data)
        self.assertIn("permissions", response.data)
        self.assertEqual(response.data["role"]["id"], self.target_role.id_rol)

    def test_create_role_requires_csrf(self):
        response = self.client.post(
            "/api/v1/roles",
            {
                "name": "SUPERVISOR_TEST",
                "description": "Rol supervisor",
                "landingRoute": "/supervisor",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_create_role_duplicate_name_returns_conflict(self):
        response = self.client.post(
            "/api/v1/roles",
            {
                "name": "MEDICO_TEST_ROLES",
                "description": "Duplicado",
                "landingRoute": "/dup",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ROLE_EXISTS")

    def test_create_role_validation_error_when_missing_fields(self):
        response = self.client.post(
            "/api/v1/roles",
            {"name": "INCOMPLETO"},
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_update_role_success(self):
        response = self.client.put(
            f"/api/v1/roles/{self.target_role.id_rol}",
            {
                "name": "MEDICO_EDITADO",
                "description": "Rol actualizado",
                "landingRoute": "/nuevo",
                "isActive": False,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("role", response.data)
        self.assertEqual(response.data["role"]["name"], "MEDICO_EDITADO")
        self.assertFalse(response.data["role"]["isActive"])

    def test_update_role_not_found_returns_404(self):
        response = self.client.put(
            "/api/v1/roles/999999",
            {
                "description": "No existe",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_update_role_duplicate_name_returns_conflict(self):
        Roles.objects.create(
            rol="ROL_DUPLICADO",
            desc_rol="Dup",
            landing_route="/dup",
            is_active=True,
        )

        response = self.client.put(
            f"/api/v1/roles/{self.target_role.id_rol}",
            {
                "name": "ROL_DUPLICADO",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ROLE_EXISTS")

    def test_update_system_role_is_blocked(self):
        response = self.client.put(
            f"/api/v1/roles/{self.system_role.id_rol}",
            {
                "description": "No deberia cambiar",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_SYSTEM_PROTECTED")

    def test_delete_system_role_is_blocked(self):
        response = self.client.delete(
            f"/api/v1/roles/{self.system_role.id_rol}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "CANNOT_DELETE_SYSTEM_ROLE")

    def test_delete_role_not_found(self):
        response = self.client.delete(
            "/api/v1/roles/999999",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_delete_role_success(self):
        response = self.client.delete(
            f"/api/v1/roles/{self.target_role.id_rol}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"success": True})

    def test_delete_role_with_active_users_returns_role_has_users(self):
        user = SyUsuario.objects.create(
            usuario="medico_activo",
            correo="medico.activo@example.com",
            clave_hash=make_password("Medico_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user,
            nombre="Medico",
            paterno="Activo",
            materno="",
        )
        RelUsuarioRol.objects.create(
            id_usuario=user, id_rol=self.target_role, is_primary=True
        )

        response = self.client.delete(
            f"/api/v1/roles/{self.target_role.id_rol}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ROLE_HAS_USERS")

    def test_permissions_catalog_contract(self):
        response = self.client.get("/api/v1/permissions")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("total", response.data)
        self.assertGreaterEqual(response.data["total"], 1)
        item = response.data["items"][0]
        self.assertIn("id", item)
        self.assertIn("code", item)
        self.assertIn("description", item)
        self.assertIn("isSystem", item)

    @override_settings(RBAC_READ_S1_ENABLED=True)
    def test_roles_list_s1_source_audit_when_flag_enabled(self):
        response = self.client.get("/api/v1/roles")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(accion="RBAC_ROLE_LIST").latest(
            "id_evento"
        )
        self.assertEqual(event.meta.get("source"), "s1")

    @override_settings(RBAC_READ_S1_ENABLED=False)
    def test_roles_list_legacy_source_audit_when_flag_disabled(self):
        response = self.client.get("/api/v1/roles")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(accion="RBAC_ROLE_LIST").latest(
            "id_evento"
        )
        self.assertEqual(event.meta.get("source"), "legacy")

    @override_settings(RBAC_ROLE_MUTATION_S2_ENABLED=True)
    def test_create_role_records_s2_source_when_mutation_flag_enabled(self):
        response = self.client.post(
            "/api/v1/roles",
            {
                "name": "SUPERVISOR_S2_CREATE",
                "description": "Rol supervisor S2",
                "landingRoute": "/supervisor-s2",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = AuditoriaEvento.objects.filter(accion="RBAC_ROLE_CREATE").latest(
            "id_evento"
        )
        self.assertEqual(event.meta.get("source"), "s2")

    @override_settings(RBAC_ROLE_MUTATION_S2_ENABLED=True)
    def test_update_role_records_s2_source_when_mutation_flag_enabled(self):
        response = self.client.put(
            f"/api/v1/roles/{self.target_role.id_rol}",
            {
                "description": "Descripcion S2",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(accion="RBAC_ROLE_UPDATE").latest(
            "id_evento"
        )
        self.assertEqual(event.meta.get("source"), "s2")

    @override_settings(RBAC_ROLE_MUTATION_S2_ENABLED=True)
    def test_delete_role_records_s2_source_when_mutation_flag_enabled(self):
        response = self.client.delete(
            f"/api/v1/roles/{self.target_role.id_rol}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(accion="RBAC_ROLE_DELETE").latest(
            "id_evento"
        )
        self.assertEqual(event.meta.get("source"), "s2")

    def test_assign_role_permissions_accepts_legacy_payload_keys(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "role_id": self.target_role.id_rol,
                "permission_ids": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["roleId"], self.target_role.id_rol)
        self.assertEqual(len(response.data["permissions"]), 1)
        self.assertEqual(response.data["permissions"][0]["code"], "agenda:read")

    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=True)
    def test_assign_role_permissions_records_s3_source_when_flag_enabled(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(
            accion="RBAC_ROLE_PERMISSIONS_ASSIGN"
        ).latest("id_evento")
        self.assertEqual(event.meta.get("source"), "s3")

    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=False)
    def test_assign_role_permissions_records_legacy_source_when_flag_disabled(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(
            accion="RBAC_ROLE_PERMISSIONS_ASSIGN"
        ).latest("id_evento")
        self.assertEqual(event.meta.get("source"), "legacy")

    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=True)
    def test_assign_role_permissions_returns_token_invalid_when_unauthenticated(self):
        self.client.cookies.clear()

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")

    def test_assign_role_permissions_auto_adds_read_dependency(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [
                    self.perm_update.id_permiso,
                    self.perm_read.id_permiso,
                ],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {item["code"] for item in response.data["permissions"]}
        self.assertIn("pacientes:read", codes)
        self.assertIn("pacientes:update", codes)

    def _active_codes(self, role):
        return set(
            RelRolPermiso.objects.filter(
                id_rol=role, fch_baja__isnull=True
            ).values_list("id_permiso__codigo", flat=True)
        )

    def _assign(self, role, permission_ids):
        return self.client.post(
            "/api/v1/permissions/assign",
            {"roleId": role.id_rol, "permissionIds": list(permission_ids)},
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

    def test_assign_only_update_persists_read_dependency(self):
        response = self._assign(self.target_role, [self.perm_update.id_permiso])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._active_codes(self.target_role),
            {"pacientes:update", "pacientes:read"},
        )

    def test_assign_usuarios_update_adds_explicit_and_inferred_dependencies(self):
        users_update = Permisos.objects.create(
            codigo="admin:gestion:usuarios:update", descripcion="u", is_active=True
        )
        for code in (
            "admin:gestion:usuarios:read",
            "admin:gestion:roles:read",
            "admin:gestion:permisos:read",
        ):
            Permisos.objects.create(codigo=code, descripcion=code, is_active=True)

        response = self._assign(self.target_role, [users_update.id_permiso])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._active_codes(self.target_role),
            {
                "admin:gestion:usuarios:update",
                "admin:gestion:usuarios:read",
                "admin:gestion:roles:read",
                "admin:gestion:permisos:read",
            },
        )

    def test_assign_ignores_nonexistent_dependency_code(self):
        users_update = Permisos.objects.create(
            codigo="admin:gestion:usuarios:update", descripcion="u", is_active=True
        )

        response = self._assign(self.target_role, [users_update.id_permiso])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._active_codes(self.target_role), {"admin:gestion:usuarios:update"}
        )

    def test_assign_fichas_create_does_not_require_read(self):
        create = Permisos.objects.create(
            codigo="recepcion:fichas:medicina_general:create",
            descripcion="c",
            is_active=True,
        )

        response = self._assign(self.target_role, [create.id_permiso])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._active_codes(self.target_role),
            {"recepcion:fichas:medicina_general:create"},
        )

    def test_assign_actor_without_dependency_gets_403_and_persists_nothing(self):
        users_update = Permisos.objects.create(
            codigo="admin:gestion:usuarios:update", descripcion="u", is_active=True
        )
        Permisos.objects.create(
            codigo="admin:gestion:roles:read", descripcion="r", is_active=True
        )
        roles_update = Permisos.objects.create(
            codigo="admin:gestion:roles:update", descripcion="ru", is_active=True
        )
        # El actor puede asignar usuarios:update, pero NO posee roles:read.
        actor_role = Roles.objects.create(
            rol="ACTOR_SIN_DEP",
            desc_rol="Actor sin dependencia",
            landing_route="/admin/roles",
            is_active=True,
        )
        for permission in (users_update, roles_update):
            RelRolPermiso.objects.create(id_rol=actor_role, id_permiso=permission)
        actor = SyUsuario.objects.create(
            usuario="actor_sin_dep",
            correo="actor.sin.dep@example.com",
            clave_hash=make_password("Actor_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=actor, nombre="Actor", paterno="Sin", materno=""
        )
        RelUsuarioRol.objects.create(
            id_usuario=actor, id_rol=actor_role, is_primary=True
        )

        self._login_as("actor_sin_dep", "Actor_123456")
        response = self._assign(self.target_role, [users_update.id_permiso])

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_GRANT_NOT_ALLOWED")
        self.assertEqual(self._active_codes(self.target_role), set())

    def test_assign_role_permissions_reactivates_soft_deleted_relation(self):
        relation = RelRolPermiso.objects.create(
            id_rol=self.target_role,
            id_permiso=self.perm_extra,
        )
        relation.fch_baja = timezone.now() - timedelta(days=1)
        relation.usr_baja = self.admin
        relation.save(update_fields=["fch_baja", "usr_baja"])

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        relation.refresh_from_db()
        self.assertIsNone(relation.fch_baja)

    def test_assign_role_permissions_updates_auth_revision_for_associated_users(self):
        target_user = SyUsuario.objects.create(
            usuario="role_sync_user",
            correo="role.sync.user@example.com",
            clave_hash=make_password("RoleSync_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=target_user,
            nombre="Role",
            paterno="Sync",
            materno="User",
        )
        RelUsuarioRol.objects.create(
            id_usuario=target_user,
            id_rol=self.target_role,
            is_primary=True,
            usr_asignacion=self.admin,
        )

        self.assertIsNone(target_user.fch_modf)

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertIsNotNone(target_user.fch_modf)

    def test_assign_role_permissions_deactivates_unrequested_relations(self):
        keep_relation = RelRolPermiso.objects.create(
            id_rol=self.target_role,
            id_permiso=self.perm_extra,
        )
        drop_relation = RelRolPermiso.objects.create(
            id_rol=self.target_role,
            id_permiso=self.perm_read,
        )

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [self.perm_extra.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        keep_relation.refresh_from_db()
        drop_relation.refresh_from_db()
        self.assertIsNone(keep_relation.fch_baja)
        self.assertIsNotNone(drop_relation.fch_baja)

    def test_assign_role_permissions_validation_error(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": "no-es-lista",
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_assign_role_permissions_with_missing_permission_returns_not_found(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.target_role.id_rol,
                "permissionIds": [999999],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "PERMISSION_NOT_FOUND")

    def test_assign_role_permissions_role_not_found(self):
        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": 999999,
                "permissionIds": [self.perm_read.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_assign_role_permissions_blocks_self_role_escalation(self):
        roles_update = CatPermiso.objects.create(
            codigo="admin:gestion:roles:update",
            descripcion="Actualizar roles",
            is_active=True,
        )
        users_update = CatPermiso.objects.create(
            codigo="admin:gestion:usuarios:update",
            descripcion="Actualizar usuarios",
            is_active=True,
        )
        limited_role = CatRol.objects.create(
            rol="LIMITED_ROLE_MANAGER",
            desc_rol="Gestor limitado",
            landing_route="/admin/roles",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=limited_role, id_permiso=roles_update)

        limited_user = SyUsuario.objects.create(
            usuario="limited_role_manager",
            correo="limited.role.manager@example.com",
            clave_hash=make_password("Limited_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=limited_user,
            nombre="Limited",
            paterno="Manager",
            materno="",
        )
        RelUsuarioRol.objects.create(
            id_usuario=limited_user, id_rol=limited_role, is_primary=True
        )

        self._login_as("limited_role_manager", "Limited_123456")

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": limited_role.id_rol,
                "permissionIds": [roles_update.id_permiso, users_update.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data["code"], "SELF_ROLE_PERMISSION_ASSIGNMENT_FORBIDDEN"
        )
        self.assertFalse(
            RelRolPermiso.objects.filter(
                id_rol=limited_role, id_permiso=users_update, fch_baja__isnull=True
            ).exists()
        )

    def test_assign_role_permissions_blocks_updating_admin_role_without_wildcard(self):
        roles_update = CatPermiso.objects.create(
            codigo="admin:gestion:roles:update",
            descripcion="Actualizar roles",
            is_active=True,
        )
        limited_role = CatRol.objects.create(
            rol="LIMITED_ADMIN_ROLE_EDITOR",
            desc_rol="Editor de roles admin",
            landing_route="/admin/roles",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=limited_role, id_permiso=roles_update)

        limited_user = SyUsuario.objects.create(
            usuario="limited_admin_editor",
            correo="limited.admin.editor@example.com",
            clave_hash=make_password("Limited_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=limited_user,
            nombre="Limited",
            paterno="Admin",
            materno="",
        )
        RelUsuarioRol.objects.create(
            id_usuario=limited_user, id_rol=limited_role, is_primary=True
        )

        self._login_as("limited_admin_editor", "Limited_123456")

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": self.admin_role.id_rol,
                "permissionIds": [roles_update.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_ADMIN_PROTECTED")

    def test_assign_role_permissions_blocks_granting_permissions_actor_does_not_have(
        self,
    ):
        roles_update = CatPermiso.objects.create(
            codigo="admin:gestion:roles:update",
            descripcion="Actualizar roles",
            is_active=True,
        )
        users_update = CatPermiso.objects.create(
            codigo="admin:gestion:usuarios:update",
            descripcion="Actualizar usuarios",
            is_active=True,
        )
        limited_role = CatRol.objects.create(
            rol="LIMITED_PERMISSION_GRANTER",
            desc_rol="Gestor sin permisos de usuarios",
            landing_route="/admin/roles",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=limited_role, id_permiso=roles_update)

        limited_user = SyUsuario.objects.create(
            usuario="limited_permission_granter",
            correo="limited.permission.granter@example.com",
            clave_hash=make_password("Limited_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=limited_user,
            nombre="Limited",
            paterno="Granter",
            materno="",
        )
        RelUsuarioRol.objects.create(
            id_usuario=limited_user, id_rol=limited_role, is_primary=True
        )

        external_role = CatRol.objects.create(
            rol="EXTERNAL_TARGET_ROLE",
            desc_rol="Rol externo",
            landing_route="/target",
            is_active=True,
        )

        self._login_as("limited_permission_granter", "Limited_123456")

        response = self.client.post(
            "/api/v1/permissions/assign",
            {
                "roleId": external_role.id_rol,
                "permissionIds": [roles_update.id_permiso, users_update.id_permiso],
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_GRANT_NOT_ALLOWED")
        self.assertFalse(
            RelRolPermiso.objects.filter(
                id_rol=external_role, id_permiso=users_update, fch_baja__isnull=True
            ).exists()
        )

    def test_revoke_read_permission_with_dependency_returns_error(self):
        RelRolPermiso.objects.create(id_rol=self.target_role, id_permiso=self.perm_read)
        RelRolPermiso.objects.create(
            id_rol=self.target_role, id_permiso=self.perm_update
        )

        response = self.client.delete(
            f"/api/v1/permissions/roles/{self.target_role.id_rol}/permissions/{self.perm_read.id_permiso}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "PERMISSION_DEPENDENCY")

    def test_revoke_permission_success(self):
        RelRolPermiso.objects.create(id_rol=self.target_role, id_permiso=self.perm_read)

        response = self.client.delete(
            f"/api/v1/permissions/roles/{self.target_role.id_rol}/permissions/{self.perm_read.id_permiso}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["roleId"], self.target_role.id_rol)
        self.assertEqual(response.data["permissions"], [])

    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=True)
    def test_revoke_permission_records_s3_source_when_flag_enabled(self):
        RelRolPermiso.objects.create(id_rol=self.target_role, id_permiso=self.perm_read)

        response = self.client.delete(
            f"/api/v1/permissions/roles/{self.target_role.id_rol}/permissions/{self.perm_read.id_permiso}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(
            accion="RBAC_ROLE_PERMISSION_REVOKE"
        ).latest("id_evento")
        self.assertEqual(event.meta.get("source"), "s3")

    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=False)
    def test_revoke_permission_records_legacy_source_when_flag_disabled(self):
        RelRolPermiso.objects.create(id_rol=self.target_role, id_permiso=self.perm_read)

        response = self.client.delete(
            f"/api/v1/permissions/roles/{self.target_role.id_rol}/permissions/{self.perm_read.id_permiso}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditoriaEvento.objects.filter(
            accion="RBAC_ROLE_PERMISSION_REVOKE"
        ).latest("id_evento")
        self.assertEqual(event.meta.get("source"), "legacy")

    def test_revoke_permission_role_not_found(self):
        response = self.client.delete(
            f"/api/v1/permissions/roles/999999/permissions/{self.perm_read.id_permiso}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_revoke_permission_not_found(self):
        response = self.client.delete(
            f"/api/v1/permissions/roles/{self.target_role.id_rol}/permissions/{self.perm_read.id_permiso}",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "PERMISSION_NOT_FOUND")
