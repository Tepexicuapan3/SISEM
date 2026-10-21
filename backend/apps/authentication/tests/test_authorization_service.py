from django.test import SimpleTestCase

from apps.authentication.services.authorization_service import (
    get_capability_state,
    has_capability,
)
from apps.authentication.services.permission_dependencies import (
    CAPABILITY_REQUIREMENTS,
)


class AuthorizationServiceTests(SimpleTestCase):
    def test_has_capability_denies_when_permission_is_missing(self):
        self.assertFalse(has_capability([], "flow.somatometria.capture"))

    def test_has_capability_allows_when_effective_permission_is_complete(self):
        self.assertTrue(
            has_capability(
                [
                    "clinico:somatometria:read",
                ],
                "flow.somatometria.capture",
            )
        )

    def test_get_capability_state_denies_unknown_capability_by_default(self):
        state = get_capability_state(
            ["clinico:somatometria:read"],
            "flow.unknown.capability",
        )

        self.assertEqual(
            state,
            {
                "granted": False,
                "missingAllOf": [],
                "missingAnyOf": [],
            },
        )

    def test_get_capability_state_reports_missing_any_of_dependencies(self):
        state = get_capability_state([], "flow.visits.queue.read")

        self.assertFalse(state["granted"])
        self.assertIn("recepcion:fichas:medicina_general:create", state["missingAnyOf"])

    def test_fichas_create_alone_grants_reception_capabilities(self):
        # Regresion: antes exigia `recepcion:fichas:*:read` (inexistente) y
        # bloqueaba la creacion de fichas a roles no-admin.
        for resource in ("medicina_general", "especialidad", "urgencias"):
            perms = [f"recepcion:fichas:{resource}:create"]
            self.assertTrue(has_capability(perms, "flow.recepcion.queue.write"))
            self.assertTrue(has_capability(perms, "flow.visits.queue.read"))

    def test_single_change_point_updates_runtime_behavior(self):
        original_requirement = CAPABILITY_REQUIREMENTS["flow.somatometria.capture"]

        try:
            CAPABILITY_REQUIREMENTS["flow.somatometria.capture"] = {
                "allOf": ["clinico:somatometria:update"]
            }

            self.assertFalse(
                has_capability(
                    [
                        "clinico:somatometria:read",
                    ],
                    "flow.somatometria.capture",
                )
            )
        finally:
            CAPABILITY_REQUIREMENTS["flow.somatometria.capture"] = original_requirement
