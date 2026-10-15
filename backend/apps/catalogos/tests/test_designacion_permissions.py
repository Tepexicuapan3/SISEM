"""Dependencias y capabilities de los permisos de designacion de autorizadores."""
from django.test import SimpleTestCase

from apps.authentication.services.permission_dependencies import (
    CAPABILITY_REQUIREMENTS,
    get_permission_dependency_closure,
    resolve_capabilities,
)

READ = "admin:autorizadores:designacion:read"
WRITE = "admin:autorizadores:designacion:write"
GLOBAL = "admin:autorizadores:designacion:global"


class DesignacionPermissionDependenciesTests(SimpleTestCase):
    def test_write_arrastra_read_y_global_arrastra_write_y_read(self):
        self.assertIn(READ, get_permission_dependency_closure(WRITE))
        closure = get_permission_dependency_closure(GLOBAL)
        self.assertIn(WRITE, closure)
        self.assertIn(READ, closure)

    def test_capabilities_registradas_para_el_frontend(self):
        for suffix, permission in (("read", READ), ("write", WRITE), ("global", GLOBAL)):
            key = f"admin.catalogs.designacionAutorizadores.{suffix}"
            self.assertEqual(CAPABILITY_REQUIREMENTS[key], {"allOf": [permission]})

    def test_global_sin_sus_dependencias_no_concede_la_capability(self):
        key = "admin.catalogs.designacionAutorizadores.global"
        self.assertFalse(resolve_capabilities([GLOBAL])[key]["granted"])
        self.assertTrue(resolve_capabilities([READ, WRITE, GLOBAL])[key]["granted"])
