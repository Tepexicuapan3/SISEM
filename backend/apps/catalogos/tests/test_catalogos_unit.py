from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import RequestFactory, TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.catalogos.permissions import CatalogApiException, HasCatalogPermission


class CatalogModelsAndPermissionsUnitTests(TestCase):
    def test_roles_and_permissions_property_aliases(self):
        role = Roles.objects.create(
            rol="PROP_ROLE",
            desc_rol="Role props",
            landing_route="/props",
            is_active=True,
        )
        permission = Permisos.objects.create(
            codigo="props:read",
            descripcion="Permiso props",
            is_active=True,
        )

        self.assertEqual(role.id, role.id_rol)
        self.assertEqual(role.name, role.rol)
        self.assertEqual(role.description, role.desc_rol)
        self.assertEqual(role.is_system, role.es_sistema)

        self.assertEqual(permission.id, permission.id_permiso)
        self.assertEqual(permission.code, permission.codigo)
        self.assertEqual(permission.name, permission.descripcion)
        self.assertEqual(permission.description, permission.descripcion)
        self.assertEqual(permission.is_system, permission.es_sistema)

    def test_has_catalog_permission_requires_action_and_catalog(self):
        # `action`/`catalog` son ahora posicionales obligatorios del
        # constructor (ver HasCatalogPermission.__init__) -- Python mismo
        # impide instanciar el permiso sin ambos, en vez de fallar mas tarde
        # en tiempo de request como antes.
        with self.assertRaises(TypeError):
            HasCatalogPermission()

    @patch("apps.catalogos.permissions.authenticate_request")
    def test_has_catalog_permission_denies_without_required_permission(self, auth_mock):
        user = SyUsuario.objects.create(
            usuario="perm_unit",
            correo="perm.unit@example.com",
            clave_hash=make_password("Perm_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        auth_mock.return_value = user

        permission = HasCatalogPermission(action="read", catalog="admin:catalogos:centros_atencion")
        request = RequestFactory().get("/api/v1/care-centers/")

        with self.assertRaises(CatalogApiException) as ctx:
            permission.has_permission(request, None)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["code"], "INSUFFICIENT_PERMISSIONS")
