from django.test import SimpleTestCase

from apps.administracion.management.seeds.navigation_permissions_seed import (
    NAVIGATION_PERMISSIONS_SEED,
)
from apps.authentication.services.permission_dependencies import (
    CAPABILITY_REQUIREMENTS,
    evaluate_permission_requirement,
    resolve_capabilities,
)

DOCS = ("ficha", "receta", "nota")


class PrintCapabilityTests(SimpleTestCase):
    def granted(self, key, perms):
        return resolve_capabilities(perms)[key]["granted"]

    def test_capabilities_registered(self):
        for d in DOCS:
            self.assertIn(f"documentos.{d}.imprimir", CAPABILITY_REQUIREMENTS)

    def test_denied_without_permissions(self):
        for d in DOCS:
            self.assertFalse(self.granted(f"documentos.{d}.imprimir", []))
            self.assertFalse(self.granted(f"documentos.{d}.imprimir", ["admin:gestion:usuarios:read"]))

    def test_ficha_granted_by_reception_or_clinical(self):
        key = "documentos.ficha.imprimir"
        self.assertTrue(
            self.granted(
                key,
                ["recepcion:fichas:urgencias:create", "recepcion:fichas:urgencias:read"],
            )
        )
        self.assertTrue(self.granted(key, ["clinico:consultas:read"]))

    def test_receta_granted_by_own_permission_or_pharmacy(self):
        key = "documentos.receta.imprimir"
        self.assertTrue(self.granted(key, ["clinico:recetas:imprimir"]))
        self.assertTrue(self.granted(key, ["farmacia:recetas:dispensar"]))
        # Leer consultas no alcanza: lo tienen perfiles de apoyo.
        self.assertFalse(self.granted(key, ["clinico:consultas:read"]))
        self.assertFalse(self.granted(key, ["recepcion:fichas:urgencias:create"]))

    def test_nota_requires_clinical_read(self):
        key = "documentos.nota.imprimir"
        self.assertTrue(self.granted(key, ["clinico:consultas:read"]))
        self.assertFalse(self.granted(key, ["farmacia:recetas:dispensar"]))

    def test_wildcard_grants_all(self):
        for d in DOCS:
            self.assertTrue(self.granted(f"documentos.{d}.imprimir", ["*"]))

    def test_no_new_permission_codes_invented(self):
        # Solo permisos que existen: usados en otras capabilities o sembrados.
        used_elsewhere = {code for code, _ in NAVIGATION_PERMISSIONS_SEED}
        for key, req in CAPABILITY_REQUIREMENTS.items():
            if key.startswith("documentos."):
                continue
            for bucket in ("allOf", "anyOf"):
                used_elsewhere.update(req.get(bucket, []))
        used_elsewhere.add("farmacia:recetas:dispensar")  # seed existente (dispensacion)
        for d in DOCS:
            req = CAPABILITY_REQUIREMENTS[f"documentos.{d}.imprimir"]
            for perm in req.get("allOf", []) + req.get("anyOf", []):
                self.assertIn(perm, used_elsewhere)
