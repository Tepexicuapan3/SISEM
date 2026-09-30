from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory

from apps.administracion.exceptions import custom_exception_handler
from apps.administracion.middleware.request_id import RequestIDMiddleware
from apps.administracion.models import (
    AuditoriaEvento,
    RelRolPermiso,
    RelUsuarioOverride,
    RelUsuarioRol,
)
from apps.administracion.services.audit_service import AuditService
from apps.administracion.services.rbac_resolver import RBACResolver
from apps.administracion.services.rbac_feature_flags import (
    is_rbac_read_s1_enabled,
    resolve_rbac_read_source,
)
from apps.administracion.use_cases.rbac_write.assign_user_roles import (
    AssignUserRolesUseCase,
)
from apps.administracion.use_cases.rbac_write.revoke_user_role import (
    RevokeUserRoleUseCase,
)
from apps.administracion.use_cases.rbac_write.set_user_primary_role import (
    SetUserPrimaryRoleUseCase,
)
from apps.administracion.use_cases.rbac_write.upsert_user_override import (
    UpsertUserOverrideUseCase,
)
from apps.administracion.use_cases.rbac_read.get_role_detail import GetRoleDetailUseCase
from apps.administracion.use_cases.rbac_read.list_permissions import (
    ListPermissionsUseCase,
)
from apps.administracion.use_cases.rbac_read.list_roles import ListRolesUseCase
from apps.administracion.repositories.rbac_read_repository import RbacReadRepository
from apps.administracion.policies.rbac_read_policy import RbacReadPolicy
from apps.administracion.services.rbac_read_serializers import (
    serialize_permission_catalog,
    serialize_role_detail,
    serialize_role_list,
)
from apps.administracion.views.rbac_read_views import resolve_read_source
from apps.administracion.views import rbac_views
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles


class RequestIDMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_preserves_existing_request_id(self):
        def get_response(_request):
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(get_response)
        request = self.factory.get("/api/test", HTTP_X_REQUEST_ID="req-existente")

        response = middleware(request)

        self.assertEqual(request.request_id, "req-existente")
        self.assertEqual(response["X-Request-ID"], "req-existente")

    def test_generates_request_id_when_missing(self):
        def get_response(_request):
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(get_response)
        request = self.factory.get("/api/test")

        response = middleware(request)

        self.assertTrue(hasattr(request, "request_id"))
        self.assertTrue(request.request_id)
        self.assertEqual(response["X-Request-ID"], request.request_id)


class CustomExceptionHandlerTests(SimpleTestCase):
    def test_returns_api_error_for_drf_exception(self):
        response = custom_exception_handler(
            ValidationError("dato invalido"), {"view": None}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "API_ERROR")
        self.assertEqual(response.data["status"], 400)

    def test_returns_internal_error_for_unhandled_exception(self):
        response = custom_exception_handler(Exception("boom"), {"view": None})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(response.data["status"], 500)

    @patch("apps.administracion.exceptions.exception_handler")
    def test_preserves_nested_detail_payload_with_details_and_request_id(
        self, handler_mock
    ):
        handler_mock.return_value = Response(
            {
                "detail": {
                    "code": "PERMISSION_DENIED",
                    "message": "No tienes permiso",
                    "details": {"field": ["error"]},
                    "requestId": "req-xyz",
                }
            },
            status=403,
        )

        response = custom_exception_handler(Exception("x"), {"view": None})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")
        self.assertEqual(response.data["requestId"], "req-xyz")
        self.assertIn("details", response.data)


class RbacResolverTests(TestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="resolver_user",
            correo="resolver.user@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Resolver",
            paterno="User",
            materno="",
        )

        self.role = Roles.objects.create(
            rol="RESOLVER_ROLE",
            desc_rol="Role resolver",
            landing_route="/resolver",
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user, id_rol=self.role, is_primary=True
        )

        self.perm_read = Permisos.objects.create(
            codigo="expedientes:read",
            descripcion="Leer expedientes",
            is_active=True,
        )
        self.perm_write = Permisos.objects.create(
            codigo="expedientes:update",
            descripcion="Actualizar expedientes",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_read)
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_write)

    def test_returns_wildcard_for_admin_role(self):
        self.role.is_admin = True
        self.role.save(update_fields=["is_admin"])

        permissions = RBACResolver.get_effective_permissions(self.user)

        self.assertEqual(permissions, ["*"])

    def test_admin_with_active_deny_override_returns_explicit_permissions(self):
        self.role.is_admin = True
        self.role.save(update_fields=["is_admin"])

        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=self.perm_write,
            efecto="DENY",
        )

        permissions = RBACResolver.get_effective_permissions(self.user)

        self.assertNotIn("*", permissions)
        self.assertIn("expedientes:read", permissions)
        self.assertNotIn("expedientes:update", permissions)

    def test_applies_allow_deny_and_ignores_expired_overrides(self):
        extra_perm = Permisos.objects.create(
            codigo="farmacia:read",
            descripcion="Leer farmacia",
            is_active=True,
        )
        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=self.perm_write,
            efecto="DENY",
        )
        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=extra_perm,
            efecto="ALLOW",
        )
        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=self.perm_read,
            efecto="DENY",
            fch_expira=timezone.now() - timedelta(days=1),
        )

        permissions = RBACResolver.get_effective_permissions(self.user)

        self.assertIn("expedientes:read", permissions)
        self.assertNotIn("expedientes:update", permissions)
        self.assertIn("farmacia:read", permissions)


class SetUserPrimaryRoleUseCaseTests(TestCase):
    def setUp(self):
        self.actor = SyUsuario.objects.create(
            usuario="set_primary_actor",
            correo="set.primary.actor@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        self.user = SyUsuario.objects.create(
            usuario="set_primary_user",
            correo="set.primary.user@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        self.role_primary = Roles.objects.create(
            rol="SET_PRIMARY_ROLE_A",
            desc_rol="Primary role A",
            landing_route="/primary-a",
            is_active=True,
        )
        self.role_secondary = Roles.objects.create(
            rol="SET_PRIMARY_ROLE_B",
            desc_rol="Primary role B",
            landing_route="/primary-b",
            is_active=True,
        )

        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=self.role_primary,
            is_primary=True,
            usr_asignacion=self.actor,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=self.role_secondary,
            is_primary=False,
            usr_asignacion=self.actor,
        )

    @patch(
        "apps.administracion.use_cases.rbac_write.set_user_primary_role.touch_user_auth_revision"
    )
    def test_updates_primary_role_and_touches_auth_revision(self, touch_revision_mock):
        result = SetUserPrimaryRoleUseCase.execute(
            actor=self.actor,
            user_id=self.user.id_usuario,
            role_id=self.role_secondary.id_rol,
            serialize_user_roles=lambda _user: [],
        )

        self.assertEqual(result["target_user"].id_usuario, self.user.id_usuario)
        self.assertEqual(result["payload"]["userId"], self.user.id_usuario)
        touch_revision_mock.assert_called_once_with(
            self.user,
            actor_id=self.actor.id_usuario,
        )

        primary_relations = RelUsuarioRol.objects.filter(
            id_usuario=self.user,
            fch_baja__isnull=True,
            is_primary=True,
        )
        self.assertEqual(primary_relations.count(), 1)
        self.assertEqual(primary_relations.first().id_rol_id, self.role_secondary.id_rol)


class RbacWriteConcurrencyHardeningUseCaseTests(TestCase):
    def setUp(self):
        self.actor = SyUsuario.objects.create(
            usuario="concurrency_actor",
            correo="concurrency.actor@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        self.target_user = SyUsuario.objects.create(
            usuario="concurrency_target",
            correo="concurrency.target@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        self.role_a = Roles.objects.create(
            rol="CONCURRENCY_ROLE_A",
            desc_rol="Role A",
            landing_route="/role-a",
            is_active=True,
        )
        self.role_b = Roles.objects.create(
            rol="CONCURRENCY_ROLE_B",
            desc_rol="Role B",
            landing_route="/role-b",
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.target_user,
            id_rol=self.role_a,
            is_primary=True,
            usr_asignacion=self.actor,
        )
        self.override_permission = Permisos.objects.create(
            codigo="concurrency:override:read",
            descripcion="Concurrency override",
            is_active=True,
        )

    @patch(
        "apps.administracion.use_cases.rbac_write.assign_user_roles.touch_user_auth_revision"
    )
    def test_assign_user_roles_recovers_from_integrity_error(self, touch_revision_mock):
        original_create = RelUsuarioRol.objects.create

        def create_side_effect(*args, **kwargs):
            original_create(
                id_usuario=self.target_user,
                id_rol=self.role_b,
                is_primary=False,
                usr_asignacion=self.actor,
            )
            raise IntegrityError("duplicate key value violates unique constraint")

        with patch(
            "apps.administracion.use_cases.rbac_write.assign_user_roles.RelUsuarioRol.objects.create",
            side_effect=create_side_effect,
        ):
            result = AssignUserRolesUseCase.execute(
                actor=self.actor,
                user_id=self.target_user.id_usuario,
                role_ids=[self.role_b.id_rol],
                serialize_user_roles=lambda user: [
                    {
                        "id": relation.id_rol_id,
                        "isPrimary": relation.is_primary,
                    }
                    for relation in RelUsuarioRol.objects.filter(
                        id_usuario=user, fch_baja__isnull=True
                    ).order_by("id_usuario_rol")
                ],
            )

        self.assertEqual(result["target_user"].id_usuario, self.target_user.id_usuario)
        self.assertEqual(
            RelUsuarioRol.objects.filter(
                id_usuario=self.target_user,
                id_rol=self.role_b,
                fch_baja__isnull=True,
            ).count(),
            1,
        )
        touch_revision_mock.assert_not_called()

    def test_set_user_primary_role_uses_select_for_update(self):
        with patch(
            "apps.administracion.use_cases.rbac_write.set_user_primary_role.RelUsuarioRol.objects.select_for_update",
            wraps=RelUsuarioRol.objects.select_for_update,
        ) as lock_mock:
            SetUserPrimaryRoleUseCase.execute(
                actor=self.actor,
                user_id=self.target_user.id_usuario,
                role_id=self.role_a.id_rol,
                serialize_user_roles=lambda _user: [],
            )

        self.assertTrue(lock_mock.called)

    def test_revoke_user_role_uses_select_for_update(self):
        RelUsuarioRol.objects.create(
            id_usuario=self.target_user,
            id_rol=self.role_b,
            is_primary=False,
            usr_asignacion=self.actor,
        )
        with patch(
            "apps.administracion.use_cases.rbac_write.revoke_user_role.RelUsuarioRol.objects.select_for_update",
            wraps=RelUsuarioRol.objects.select_for_update,
        ) as lock_mock:
            RevokeUserRoleUseCase.execute(
                actor=self.actor,
                user_id=self.target_user.id_usuario,
                role_id=self.role_a.id_rol,
                serialize_user_roles=lambda _user: [],
            )

        self.assertTrue(lock_mock.called)

    @patch(
        "apps.administracion.use_cases.rbac_write.upsert_user_override.touch_user_auth_revision"
    )
    @patch(
        "apps.administracion.use_cases.rbac_write.upsert_user_override.UserRepository.build_auth_user"
    )
    def test_upsert_user_override_recovers_from_integrity_error(
        self,
        build_auth_user_mock,
        touch_revision_mock,
    ):
        build_auth_user_mock.return_value = {"permissions": ["*"]}

        original_create = RelUsuarioOverride.objects.create

        def create_side_effect(*args, **kwargs):
            original_create(
                id_usuario=self.target_user,
                id_permiso=self.override_permission,
                efecto="ALLOW",
                usr_asignacion=self.actor,
            )
            raise IntegrityError("duplicate key value violates unique constraint")

        with patch(
            "apps.administracion.use_cases.rbac_write.upsert_user_override.RelUsuarioOverride.objects.create",
            side_effect=create_side_effect,
        ):
            result = UpsertUserOverrideUseCase.execute(
                actor=self.actor,
                user_id=self.target_user.id_usuario,
                permission_code=self.override_permission.codigo,
                effect="DENY",
                expires_at_raw=None,
                parse_expires_at=lambda value: value,
                serialize_user_overrides=lambda user: [
                    {
                        "id": override.id_override,
                        "effect": override.efecto,
                    }
                    for override in RelUsuarioOverride.objects.filter(
                        id_usuario=user,
                        fch_baja__isnull=True,
                    ).order_by("id_override")
                ],
            )

        self.assertEqual(result["target_user"].id_usuario, self.target_user.id_usuario)
        override = RelUsuarioOverride.objects.get(
            id_usuario=self.target_user,
            id_permiso=self.override_permission,
        )
        self.assertEqual(override.efecto, "DENY")
        self.assertIsNone(override.fch_baja)
        touch_revision_mock.assert_called_once()


class AuditServiceTests(TestCase):
    def test_log_event_persists_audit_row(self):
        user = SyUsuario.objects.create(
            usuario="audit_service_user",
            correo="audit.service.user@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        request = APIRequestFactory().get("/api/v1/roles")
        request.user = user
        request.request_id = "req-audit-service"
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        request.META["HTTP_USER_AGENT"] = "audit-test"

        AuditService.log_event(
            request=request,
            accion="RBAC_ROLE_LIST",
            recurso_tipo="role",
            recurso_id=1,
            resultado="SUCCESS",
        )

        event = AuditoriaEvento.objects.get(request_id="req-audit-service")
        self.assertEqual(event.accion, "RBAC_ROLE_LIST")
        self.assertEqual(event.recurso_tipo, "role")
        self.assertEqual(event.recurso_id, 1)
        self.assertEqual(event.ip_origen, "10.0.0.5")


class RbacViewHelpersTests(TestCase):
    def test_parse_bool_helper(self):
        self.assertTrue(rbac_views._parse_bool("true"))
        self.assertFalse(rbac_views._parse_bool("false"))
        self.assertEqual(rbac_views._parse_bool("x"), "invalid")
        self.assertIsNone(rbac_views._parse_bool(None))

    def test_parse_pagination_range_error(self):
        raw_request = APIRequestFactory().get("/api/v1/roles?page=0&pageSize=101")
        request = APIView().initialize_request(raw_request)

        page, page_size, error = rbac_views._parse_pagination(request)

        self.assertIsNone(page)
        self.assertIsNone(page_size)
        self.assertIsNotNone(error)
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.data["code"], "VALIDATION_ERROR")

    def test_user_name_and_user_ref_helpers(self):
        user = SyUsuario.objects.create(
            usuario="helper_user",
            correo="helper.user@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        self.assertEqual(rbac_views._user_name(None), "")
        self.assertEqual(rbac_views._user_name(user), "helper_user")

        with patch(
            "apps.administracion.views.rbac_views.UserRepository.get_by_id",
            return_value=None,
        ):
            self.assertEqual(
                rbac_views._user_ref_by_id(10, fallback_system=True),
                {"id": 0, "name": "Sistema"},
            )
            self.assertIsNone(rbac_views._user_ref_by_id(10, fallback_system=False))

    def test_split_permission_code_invalid(self):
        resource, action = rbac_views._split_permission_code("invalid")
        self.assertIsNone(resource)
        self.assertIsNone(action)

    def test_parse_expires_at_end_of_day_from_date_string(self):
        parsed = rbac_views._parse_expires_at_end_of_day("2030-01-02")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.hour, 23)
        self.assertEqual(parsed.minute, 59)
        self.assertEqual(parsed.second, 59)
        self.assertEqual(parsed.microsecond, 999999)

    def test_parse_expires_at_end_of_day_invalid_date(self):
        parsed = rbac_views._parse_expires_at_end_of_day("fecha-invalida")

        self.assertEqual(parsed, "invalid")

    def test_serialize_user_list_item_uses_first_role_when_no_primary(self):
        user = SyUsuario.objects.create(
            usuario="helper_user_roles",
            correo="helper.user.roles@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user,
            nombre="Helper",
            paterno="Roles",
            materno="",
        )
        role = Roles.objects.create(
            rol="HELPER_ROLE_NO_PRIMARY",
            desc_rol="Role helper",
            landing_route="/helper",
            is_active=True,
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=False)

        payload = rbac_views._serialize_user_list_item(user)

        self.assertEqual(payload["primaryRole"], "HELPER_ROLE_NO_PRIMARY")

    @patch("apps.administracion.views.rbac_views.authenticate_request")
    def test_authorize_handles_auth_service_error(self, auth_mock):
        auth_mock.side_effect = rbac_views.AuthServiceError(
            "TOKEN_INVALID", "Token invalido", 401
        )
        request = APIRequestFactory().get("/api/v1/roles")

        user, error = rbac_views._authorize(request, "admin:gestion:roles:read")

        self.assertIsNone(user)
        self.assertIsNotNone(error)
        self.assertEqual(error.status_code, 401)
        self.assertEqual(error.data["code"], "TOKEN_INVALID")

    @patch("apps.administracion.views.rbac_views.AuditoriaEvento.objects.create")
    def test_audit_swallows_internal_errors(self, create_mock):
        create_mock.side_effect = RuntimeError("db down")
        request = APIRequestFactory().get("/api/v1/roles")
        request.user = SimpleNamespace(is_authenticated=False)

        result = rbac_views._audit(request, "RBAC_TEST", "role")

        self.assertIsNone(result)


class RbacReadPolicyAndUseCaseTests(TestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="s1_policy_user",
            correo="s1.policy.user@example.com",
            clave_hash="hash",
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        self.role = Roles.objects.create(
            rol="S1_POLICY_ROLE",
            desc_rol="Role S1 policy",
            landing_route="/s1",
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user, id_rol=self.role, is_primary=True
        )
        self.perm_roles_read = Permisos.objects.create(
            codigo="admin:gestion:roles:read",
            descripcion="Leer roles",
            is_active=True,
        )
        self.perm_permissions_read = Permisos.objects.create(
            codigo="admin:gestion:permisos:read",
            descripcion="Leer permisos",
            is_active=True,
        )
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_roles_read)
        RelRolPermiso.objects.create(
            id_rol=self.role, id_permiso=self.perm_permissions_read
        )

        self.target_role = Roles.objects.create(
            rol="S1_TARGET_ROLE",
            desc_rol="Role S1 target",
            landing_route="/target",
            is_active=True,
        )
        self.target_permission = Permisos.objects.create(
            codigo="catalogo:s1:read",
            descripcion="Permiso S1",
            is_active=True,
        )
        RelRolPermiso.objects.create(
            id_rol=self.target_role, id_permiso=self.target_permission
        )

    @patch("apps.administracion.policies.rbac_read_policy.authenticate_request")
    @patch(
        "apps.administracion.policies.rbac_read_policy.UserRepository.build_auth_user"
    )
    def test_rbac_read_policy_authorize_allows_atomic_permission(
        self, build_auth_user_mock, authenticate_mock
    ):
        authenticate_mock.return_value = self.user
        build_auth_user_mock.return_value = {
            "permissions": [
                "admin:gestion:roles:read",
                "admin:gestion:permisos:read",
            ]
        }
        request = APIRequestFactory().get("/api/v1/roles")
        user, error = RbacReadPolicy.authorize(request, "admin:gestion:roles:read")

        self.assertEqual(user.id_usuario, self.user.id_usuario)
        self.assertIsNone(error)

    def test_rbac_read_repository_and_use_cases_return_read_models(self):
        repository = RbacReadRepository()

        roles_payload = ListRolesUseCase(repository).execute(page=1, page_size=10)
        detail_payload = GetRoleDetailUseCase(repository).execute(
            role_id=self.target_role.id_rol
        )
        permissions_payload = ListPermissionsUseCase(repository).execute()

        self.assertIn("items", serialize_role_list(roles_payload, repository))
        self.assertEqual(
            serialize_role_detail(detail_payload)["role"]["id"], self.target_role.id_rol
        )
        self.assertGreaterEqual(
            serialize_permission_catalog(permissions_payload)["total"], 1
        )


class RbacReadToggleTests(SimpleTestCase):
    @override_settings(RBAC_READ_SLICE_SOURCE="s1", RBAC_READ_S1_ENABLED=False)
    def test_resolve_read_source_prioritizes_explicit_s1(self):
        self.assertEqual(resolve_read_source(), "s1")
        self.assertEqual(resolve_rbac_read_source(), "s1")
        self.assertTrue(is_rbac_read_s1_enabled())

    @override_settings(RBAC_READ_SLICE_SOURCE="legacy", RBAC_READ_S1_ENABLED=True)
    def test_resolve_read_source_prioritizes_explicit_legacy(self):
        self.assertEqual(resolve_read_source(), "legacy")
        self.assertEqual(resolve_rbac_read_source(), "legacy")
        self.assertFalse(is_rbac_read_s1_enabled())

    @override_settings(RBAC_READ_SLICE_SOURCE="auto", RBAC_READ_S1_ENABLED=True)
    def test_resolve_read_source_falls_back_to_legacy_flag_when_auto(self):
        self.assertEqual(resolve_read_source(), "s1")
        self.assertEqual(resolve_rbac_read_source(), "s1")
        self.assertTrue(is_rbac_read_s1_enabled())

    @override_settings(RBAC_READ_SLICE_SOURCE="invalid", RBAC_READ_S1_ENABLED=False)
    def test_resolve_read_source_uses_legacy_for_invalid_value(self):
        self.assertEqual(resolve_read_source(), "legacy")
        self.assertEqual(resolve_rbac_read_source(), "legacy")
        self.assertFalse(is_rbac_read_s1_enabled())

    @override_settings(RBAC_READ_SLICE_SOURCE="  S1  ", RBAC_READ_S1_ENABLED=False)
    def test_resolve_read_source_normalizes_whitespace_and_case(self):
        self.assertEqual(resolve_read_source(), "s1")
        self.assertEqual(resolve_rbac_read_source(), "s1")
        self.assertTrue(is_rbac_read_s1_enabled())


class RbacRoleMutationToggleTests(SimpleTestCase):
    @override_settings(RBAC_ROLE_MUTATION_S2_ENABLED=True)
    def test_role_mutation_toggle_returns_true_when_enabled(self):
        self.assertTrue(rbac_views._is_rbac_role_mutation_s2_enabled())

    @override_settings(RBAC_ROLE_MUTATION_S2_ENABLED=False)
    def test_role_mutation_toggle_returns_false_when_disabled(self):
        self.assertFalse(rbac_views._is_rbac_role_mutation_s2_enabled())


class RbacRolePermissionToggleTests(SimpleTestCase):
    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=True)
    def test_role_permission_toggle_returns_true_when_enabled(self):
        self.assertTrue(rbac_views._is_rbac_role_permission_s3_enabled())

    @override_settings(RBAC_ROLE_PERMISSION_S3_ENABLED=False)
    def test_role_permission_toggle_returns_false_when_disabled(self):
        self.assertFalse(rbac_views._is_rbac_role_permission_s3_enabled())
