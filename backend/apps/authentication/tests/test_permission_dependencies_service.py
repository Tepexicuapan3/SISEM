from django.test import SimpleTestCase

from apps.authentication.services.permission_dependencies import (
    build_permission_context,
    evaluate_permission_dependencies,
    get_permission_dependency_closure,
    get_permission_direct_dependencies,
)


class PermissionDependenciesServiceTests(SimpleTestCase):
    def test_get_permission_dependency_closure_returns_users_update_chain(self):
        closure = get_permission_dependency_closure("admin:gestion:usuarios:update")

        self.assertEqual(
            closure,
            [
                "admin:gestion:permisos:read",
                "admin:gestion:roles:read",
                "admin:gestion:usuarios:read",
                "admin:gestion:usuarios:update",
            ],
        )

    def test_evaluate_permission_dependencies_denies_when_chain_is_incomplete(self):
        state = evaluate_permission_dependencies(
            "admin:gestion:usuarios:update",
            [
                "admin:gestion:usuarios:update",
                "admin:gestion:usuarios:read",
            ],
        )

        self.assertFalse(state["granted"])
        self.assertEqual(
            state["missingPermissions"],
            ["admin:gestion:permisos:read", "admin:gestion:roles:read"],
        )

    def test_build_permission_context_projects_effective_permissions(self):
        context = build_permission_context(
            [
                "admin:gestion:usuarios:update",
                "admin:gestion:usuarios:read",
            ]
        )

        self.assertEqual(
            context["effectivePermissions"],
            ["admin:gestion:usuarios:read"],
        )
        self.assertFalse(context["capabilities"]["admin.users.update"]["granted"])
        self.assertTrue(context["capabilities"]["admin.users.read"]["granted"])

    def test_build_permission_context_with_wildcard_marks_capabilities_as_granted(self):
        context = build_permission_context(["*"])

        self.assertEqual(context["effectivePermissions"], ["*"])
        self.assertTrue(context["capabilities"]["admin.users.editFull"]["granted"])

    def test_build_permission_context_exposes_strict_capability_prefixes(self):
        context = build_permission_context(["clinico:somatometria:read"])

        self.assertEqual(
            context["strictCapabilityPrefixes"],
            [
                "flow.recepcion.",
                "flow.somatometria.",
                "flow.visits.",
            ],
        )

    def test_build_permission_context_resolves_flow_somatometria_capabilities(self):
        context = build_permission_context(["clinico:somatometria:read"])

        self.assertTrue(context["capabilities"]["flow.somatometria.queue.read"]["granted"])
        self.assertTrue(context["capabilities"]["flow.somatometria.capture"]["granted"])
        self.assertTrue(context["capabilities"]["flow.visits.queue.read"]["granted"])

    def test_build_permission_context_resolves_flow_doctor_capabilities(self):
        context = build_permission_context(["clinico:consultas:read"])

        self.assertTrue(context["capabilities"]["flow.doctor.queue.read"]["granted"])
        self.assertTrue(
            context["capabilities"]["flow.doctor.consultation.start"]["granted"]
        )
        self.assertTrue(
            context["capabilities"]["flow.doctor.consultation.close"]["granted"]
        )

    def test_fichas_create_is_self_sufficient_without_nonexistent_read(self):
        # Bug fichas-permission-dependency-bug: `recepcion:fichas:<x>:read` no
        # existe en el catalogo, asi que la dependencia inferida dejaba el
        # permiso `create` sin efecto para roles no-admin.
        for resource in ("medicina_general", "especialidad", "urgencias"):
            code = f"recepcion:fichas:{resource}:create"
            self.assertEqual(get_permission_dependency_closure(code), [code])

            context = build_permission_context([code])

            self.assertEqual(context["effectivePermissions"], [code])
            self.assertTrue(context["capabilities"]["flow.visits.queue.read"]["granted"])
            self.assertTrue(context["capabilities"]["flow.recepcion.queue.write"]["granted"])
            self.assertTrue(context["capabilities"]["documentos.ficha.imprimir"]["granted"])
            # No concede nada mas de lo debido.
            self.assertFalse(context["capabilities"]["flow.somatometria.capture"]["granted"])
            self.assertFalse(context["capabilities"]["flow.doctor.queue.read"]["granted"])

    def test_fichas_create_exemption_does_not_affect_other_write_permissions(self):
        self.assertEqual(
            get_permission_direct_dependencies("clinico:somatometria:update"),
            ["clinico:somatometria:read"],
        )
        self.assertEqual(
            get_permission_direct_dependencies("admin:gestion:roles:update"),
            ["admin:gestion:permisos:read", "admin:gestion:roles:read"],
        )

    def test_evaluate_permission_dependencies_handles_empty_permission_code(self):
        state = evaluate_permission_dependencies("   ", ["admin:gestion:usuarios:read"])

        self.assertEqual(
            state,
            {
                "granted": False,
                "requiredPermissions": [],
                "missingPermissions": [],
            },
        )

    def test_get_permission_dependency_closure_returns_empty_for_blank_permission_code(self):
        self.assertEqual(get_permission_dependency_closure("   "), [])

    def test_modulos_write_actions_imply_modulos_read(self):
        """
        `admin:gestion:modulos:{create,update,delete}` (change
        menu-modulos-crud-ui) no tiene entrada explicita en
        EXPLICIT_PERMISSION_DEPENDENCIES: `_infer_read_dependency` ya cubre
        el caso porque `create`/`update`/`delete` estan en WRITE_ACTIONS y
        el codigo sigue el patron `recurso:accion`. Este test fija ese
        comportamiento para que no se rompa en silencio si alguien cambia
        WRITE_ACTIONS o el formato de los codigos.
        """
        for action in ("create", "update", "delete"):
            with self.subTest(action=action):
                closure = get_permission_dependency_closure(
                    f"admin:gestion:modulos:{action}"
                )
                self.assertEqual(
                    closure,
                    sorted(
                        {
                            f"admin:gestion:modulos:{action}",
                            "admin:gestion:modulos:read",
                        }
                    ),
                )

    def test_clinico_somatometria_update_infers_read_dependency(self):
        """
        D6 (change `somatometria-modulo-integral`): `clinico:somatometria:update`
        no tiene entrada explicita en EXPLICIT_PERMISSION_DEPENDENCIES --
        `_infer_read_dependency` debe derivar `clinico:somatometria:read`
        solo porque `update` esta en WRITE_ACTIONS, sin tocar ese set
        global. Si esto se rompe, un usuario con `:update` pero sin
        `:read` quedaria con la capability `flow.somatometria.edit`
        otorgada pero sin poder leer -- inconsistente.
        """
        closure = get_permission_dependency_closure("clinico:somatometria:update")

        self.assertEqual(
            closure,
            sorted({"clinico:somatometria:read", "clinico:somatometria:update"}),
        )

    def test_flow_somatometria_edit_capability_requires_update_permission(self):
        """
        D6: `flow.somatometria.edit` esta sobre `clinico:somatometria:update`
        (NO `:edit`, ese verbo no existe en WRITE_ACTIONS). Con solo
        `:read` (captura) la capability de edicion NO debe otorgarse;
        agregando `:update` si.
        """
        capture_only_context = build_permission_context(["clinico:somatometria:read"])
        self.assertFalse(
            capture_only_context["capabilities"]["flow.somatometria.edit"]["granted"]
        )
        # La capability de captura sigue intacta (D6: no se toca).
        self.assertTrue(
            capture_only_context["capabilities"]["flow.somatometria.capture"]["granted"]
        )

        with_update_context = build_permission_context(
            ["clinico:somatometria:read", "clinico:somatometria:update"]
        )
        self.assertTrue(
            with_update_context["capabilities"]["flow.somatometria.edit"]["granted"]
        )

    def test_flow_somatometria_edit_capability_denied_with_update_alone(self):
        """
        D6/gotcha confirmado: `_infer_read_dependency` agrega
        `clinico:somatometria:read` a la CLAUSURA DE REQUISITOS de
        `:update` (ver `test_clinico_somatometria_update_infers_read_dependency`),
        pero eso NO implica que otorgar solo `:update` alcance -- el
        usuario/rol debe tener AMBOS permisos efectivamente concedidos
        (`granted_permissions`). Es el mismo patron que
        `admin:gestion:usuarios:update` (requiere `roles:read` +
        `permisos:read` concedidos aparte). El rol real (`seed_e2e.py`
        CLINICO) por eso otorga `clinico:somatometria:read` Y
        `clinico:somatometria:update` juntos, nunca solo el segundo.
        """
        context = build_permission_context(["clinico:somatometria:update"])
        self.assertFalse(context["capabilities"]["flow.somatometria.edit"]["granted"])
