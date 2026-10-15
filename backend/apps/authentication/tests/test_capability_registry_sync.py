"""
Anti-drift: toda capability `admin.*` que use el frontend tiene que existir
en `CAPABILITY_REQUIREMENTS`.

El frontend trata `admin.` como prefijo ESTRICTO
(`usePermissionDependencies.ts`, KAN49_STRICT_CAPABILITY_PREFIXES): si el
backend no proyecta la capability, `hasCapability` devuelve false aunque el
usuario tenga `permissions: ["*"]`. Una key olvidada deja la pantalla
bloqueada para TODOS, incluido admin ("No tienes acceso para consultar este
catalogo"). Ver docs/domains/auth-access/permissions-source-of-truth.md (seccion 10).
"""

import re
from pathlib import Path
from unittest import SkipTest

from django.test import SimpleTestCase

from apps.authentication.services.permission_dependencies import (
    CAPABILITY_REQUIREMENTS,
)

FRONTEND_SRC = Path(__file__).resolve().parents[4] / "frontend" / "src"

# Literal "admin.<grupo>.<resto>" entre comillas simples, dobles o backticks.
ADMIN_CAPABILITY_LITERAL = re.compile(
    r"""["'`](admin\.[A-Za-z_]+\.[A-Za-z0-9_.-]+)["'`]"""
)


def _is_test_file(path: Path) -> bool:
    posix = path.as_posix()
    return "/test/" in posix or ".test." in path.name or ".spec." in path.name


def _frontend_admin_capabilities() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted(FRONTEND_SRC.rglob("*.ts*")):
        if _is_test_file(path):
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in ADMIN_CAPABILITY_LITERAL.finditer(line):
                relative = path.relative_to(FRONTEND_SRC).as_posix()
                found.setdefault(match.group(1), f"{relative}:{line_number}")
    return found


class CapabilityRegistrySyncTests(SimpleTestCase):
    def test_every_frontend_admin_capability_is_registered_in_backend(self):
        if not FRONTEND_SRC.is_dir():
            raise SkipTest("frontend/src no esta disponible (ej. contenedor solo backend)")

        found = _frontend_admin_capabilities()
        self.assertTrue(found, "No se encontro ninguna capability admin.* en el frontend")

        missing = {
            key: location
            for key, location in found.items()
            if key not in CAPABILITY_REQUIREMENTS
        }

        self.assertEqual(
            missing,
            {},
            "Capabilities usadas en el frontend sin registrar en "
            "CAPABILITY_REQUIREMENTS (permission_dependencies.py). Quedan "
            "bloqueadas para TODOS, incluido admin:\n"
            + "\n".join(f"  {key}  ({location})" for key, location in sorted(missing.items())),
        )
