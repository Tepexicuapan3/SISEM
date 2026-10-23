from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone

from apps.administracion.models import RelRolPermiso, RelUsuarioOverride, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.repositories.user_repository import UserRepository
from apps.catalogos.models import Permisos, Roles


class AuthPermissionsTests(TestCase):
    def setUp(self):
        self.user = SyUsuario.objects.create(
            usuario="admin",
            correo="admin@example.com",
            clave_hash=make_password("Clave_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Admin",
            paterno="User",
            materno="",
        )

    def test_build_auth_user_sets_admin_permissions_and_capabilities(self):
        role = Roles.objects.create(
            rol="ADMIN",
            desc_rol="Administrador",
            landing_route="/admin",
            is_admin=True,
        )
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=role, is_primary=True)

        auth_user = UserRepository.build_auth_user(self.user)

        self.assertEqual(auth_user["permissions"], ["*"])
        self.assertEqual(auth_user["effectivePermissions"], ["*"])
        self.assertEqual(auth_user["permissionDependenciesVersion"], "v1")
        self.assertEqual(
            auth_user["strictCapabilityPrefixes"],
            [
                "flow.recepcion.",
                "flow.somatometria.",
                "flow.visits.",
            ],
        )
        self.assertTrue(auth_user["authRevision"])
        self.assertTrue(auth_user["capabilities"]["admin.users.editFull"]["granted"])
        self.assertEqual(auth_user["roles"], ["ADMIN"])
        self.assertEqual(auth_user["primaryRole"], "ADMIN")

    def test_build_auth_user_applies_active_deny_override_for_admin_role(self):
        role = Roles.objects.create(
            rol="ADMIN_DENY",
            desc_rol="Administrador con deny",
            landing_route="/admin",
            is_admin=True,
        )
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=role, is_primary=True)

        denied_permission = Permisos.objects.get_or_create(codigo="admin:gestion:usuarios:update", defaults=dict(descripcion="Actualizar usuarios", is_active=True))[0]
        allowed_permission = Permisos.objects.get_or_create(codigo="admin:gestion:usuarios:read", defaults=dict(descripcion="Leer usuarios", is_active=True))[0]

        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=denied_permission,
            efecto="DENY",
        )

        auth_user = UserRepository.build_auth_user(self.user)

        self.assertNotIn("*", auth_user["permissions"])
        self.assertNotIn(denied_permission.codigo, auth_user["permissions"])
        self.assertIn(allowed_permission.codigo, auth_user["permissions"])
        self.assertNotIn(denied_permission.codigo, auth_user["effectivePermissions"])
        self.assertFalse(auth_user["capabilities"]["admin.users.update"]["granted"])

    def test_build_auth_user_applies_allow_and_deny_overrides(self):
        role = Roles.objects.create(
            rol="MEDICO",
            desc_rol="Medico",
            landing_route="/expedientes",
        )
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=role, is_primary=True)

        perm_read = Permisos.objects.get_or_create(codigo="expedientes:read", defaults=dict(descripcion="Leer"))[0]
        perm_write = Permisos.objects.get_or_create(codigo="expedientes:write", defaults=dict(descripcion="Escribir"))[0]
        perm_extra = Permisos.objects.get_or_create(codigo="pacientes:read", defaults=dict(descripcion="Leer pacientes"))[0]
        RelRolPermiso.objects.create(id_rol=role, id_permiso=perm_read)
        RelRolPermiso.objects.create(id_rol=role, id_permiso=perm_write)

        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=perm_write,
            efecto="DENY",
        )
        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=perm_extra,
            efecto="ALLOW",
        )

        auth_user = UserRepository.build_auth_user(self.user)

        self.assertIn("expedientes:read", auth_user["permissions"])
        self.assertIn("pacientes:read", auth_user["permissions"])
        self.assertNotIn("expedientes:write", auth_user["permissions"])

    def test_build_auth_user_ignores_expired_overrides(self):
        role = Roles.objects.create(
            rol="MEDICO",
            desc_rol="Medico",
            landing_route="/expedientes",
        )
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=role, is_primary=True)

        perm_read = Permisos.objects.get_or_create(codigo="expedientes:read", defaults=dict(descripcion="Leer"))[0]
        RelRolPermiso.objects.create(id_rol=role, id_permiso=perm_read)

        RelUsuarioOverride.objects.create(
            id_usuario=self.user,
            id_permiso=perm_read,
            efecto="DENY",
            fch_expira=timezone.now() - timedelta(days=1),
        )

        auth_user = UserRepository.build_auth_user(self.user)

        self.assertIn("expedientes:read", auth_user["permissions"])

    def test_build_auth_user_returns_defaults_when_user_has_no_roles(self):
        auth_user = UserRepository.build_auth_user(self.user)

        self.assertEqual(auth_user["roles"], [])
        self.assertEqual(auth_user["permissions"], [])
        self.assertEqual(auth_user["landingRoute"], None)

    def test_build_auth_user_sets_requires_onboarding_flag_from_user_state(self):
        self.user.cambiar_clave = True
        self.user.terminos_acept = False
        self.user.save(update_fields=["cambiar_clave", "terminos_acept"])

        auth_user = UserRepository.build_auth_user(self.user)

        self.assertTrue(auth_user["requiresOnboarding"])
