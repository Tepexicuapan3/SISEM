from django.test import SimpleTestCase

from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_state_machine_usecase import (
    ROLE_AUTORIZADOR_NOTA,
    ROLE_DOCTOR,
    ROLE_RECEPCION,
    ROLE_SOMATOMETRIA,
    VISIT_STATES,
    get_transition_matrix,
    transition_visit_state,
)

VALID_TRANSITIONS = {
    ("en_espera", "en_somatometria"),
    ("en_espera", "cancelada"),
    ("en_espera", "no_show"),
    ("en_somatometria", "lista_para_doctor"),
    ("lista_para_doctor", "en_consulta"),
    ("en_consulta", "cerrada"),
    # change cancelacion-nota-cascada: cancelacion post-cierre.
    ("cerrada", "cancelada"),
}


class VisitStateMachineUseCaseTests(SimpleTestCase):
    def test_valid_transitions(self):
        cases = [
            {
                "current_state": "en_espera",
                "target_state": "en_somatometria",
                "role": ROLE_RECEPCION,
            },
            {
                "current_state": "en_espera",
                "target_state": "cancelada",
                "role": ROLE_RECEPCION,
                "motivo": "El paciente solicito reagendar.",
            },
            {
                "current_state": "en_espera",
                "target_state": "no_show",
                "role": ROLE_RECEPCION,
            },
            {
                "current_state": "en_somatometria",
                "target_state": "lista_para_doctor",
                "role": ROLE_SOMATOMETRIA,
                "vitals_complete": True,
            },
            {
                "current_state": "lista_para_doctor",
                "target_state": "en_consulta",
                "role": ROLE_DOCTOR,
            },
            {
                "current_state": "en_consulta",
                "target_state": "cerrada",
                "role": ROLE_DOCTOR,
                "primary_diagnosis": "Infeccion respiratoria",
                "final_note": "Paciente estable, seguimiento ambulatorio.",
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                result = transition_visit_state(
                    case["current_state"],
                    case["target_state"],
                    case["role"],
                    vitals_complete=case.get("vitals_complete", False),
                    primary_diagnosis=case.get("primary_diagnosis"),
                    final_note=case.get("final_note"),
                    motivo=case.get("motivo"),
                )

                self.assertEqual(result, case["target_state"])

    def test_invalid_transitions_raise_visit_state_invalid(self):
        roles_by_state = {
            "en_espera": ROLE_RECEPCION,
            "en_somatometria": ROLE_SOMATOMETRIA,
            "lista_para_doctor": ROLE_DOCTOR,
            "en_consulta": ROLE_DOCTOR,
            "cerrada": ROLE_DOCTOR,
            "cancelada": ROLE_RECEPCION,
            "no_show": ROLE_RECEPCION,
        }

        for current_state in VISIT_STATES:
            for target_state in VISIT_STATES:
                if (current_state, target_state) in VALID_TRANSITIONS:
                    continue

                with self.subTest(
                    current_state=current_state,
                    target_state=target_state,
                ):
                    with self.assertRaises(VisitDomainError) as raised:
                        transition_visit_state(
                            current_state,
                            target_state,
                            roles_by_state[current_state],
                            vitals_complete=True,
                            primary_diagnosis="Dx",
                            final_note="Nota final",
                        )

                    self.assertEqual(raised.exception.code, "VISIT_STATE_INVALID")
                    self.assertEqual(raised.exception.status_code, 409)

    def test_role_restrictions_raise_role_not_allowed(self):
        cases = [
            {
                "current_state": "en_espera",
                "target_state": "en_somatometria",
                "role": ROLE_DOCTOR,
            },
            {
                "current_state": "en_espera",
                "target_state": "cancelada",
                "role": ROLE_DOCTOR,
            },
            {
                "current_state": "en_espera",
                "target_state": "no_show",
                "role": ROLE_DOCTOR,
            },
            {
                "current_state": "en_somatometria",
                "target_state": "lista_para_doctor",
                "role": ROLE_RECEPCION,
                "vitals_complete": True,
            },
            {
                "current_state": "lista_para_doctor",
                "target_state": "en_consulta",
                "role": ROLE_RECEPCION,
            },
            {
                "current_state": "en_consulta",
                "target_state": "cerrada",
                "role": ROLE_RECEPCION,
                "primary_diagnosis": "Dx",
                "final_note": "Nota final",
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(VisitDomainError) as raised:
                    transition_visit_state(
                        case["current_state"],
                        case["target_state"],
                        case["role"],
                        vitals_complete=case.get("vitals_complete", False),
                        primary_diagnosis=case.get("primary_diagnosis"),
                        final_note=case.get("final_note"),
                    )

                self.assertEqual(raised.exception.code, "ROLE_NOT_ALLOWED")
                self.assertEqual(raised.exception.status_code, 403)

    def test_guard_clause_requires_complete_vitals(self):
        with self.assertRaises(VisitDomainError) as raised:
            transition_visit_state(
                "en_somatometria",
                "lista_para_doctor",
                ROLE_SOMATOMETRIA,
            )

        self.assertEqual(raised.exception.code, "VITALS_INCOMPLETE")
        self.assertEqual(raised.exception.status_code, 422)

    def test_guard_clause_requires_primary_diagnosis_and_final_note(self):
        cases = [
            {"primary_diagnosis": None, "final_note": "Nota final"},
            {"primary_diagnosis": "Dx", "final_note": None},
            {"primary_diagnosis": "", "final_note": "Nota final"},
            {"primary_diagnosis": "Dx", "final_note": ""},
            {"primary_diagnosis": "  ", "final_note": "Nota final"},
            {"primary_diagnosis": "Dx", "final_note": "  "},
        ]

        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(VisitDomainError) as raised:
                    transition_visit_state(
                        "en_consulta",
                        "cerrada",
                        ROLE_DOCTOR,
                        primary_diagnosis=case["primary_diagnosis"],
                        final_note=case["final_note"],
                    )

                self.assertEqual(raised.exception.code, "VISIT_STATE_INVALID")
                self.assertEqual(raised.exception.status_code, 409)

    def test_unknown_states_raise_visit_state_invalid(self):
        cases = [
            {"current_state": "desconocido", "target_state": "en_espera"},
            {"current_state": "en_espera", "target_state": "desconocido"},
        ]

        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(VisitDomainError) as raised:
                    transition_visit_state(
                        case["current_state"],
                        case["target_state"],
                        ROLE_RECEPCION,
                    )

                self.assertEqual(raised.exception.code, "VISIT_STATE_INVALID")
                self.assertEqual(raised.exception.status_code, 409)

    def test_guard_clause_requires_motivo_to_cancel(self):
        for motivo_invalido in (None, "", "   "):
            with self.subTest(motivo=motivo_invalido):
                with self.assertRaises(VisitDomainError) as raised:
                    transition_visit_state(
                        "en_espera",
                        "cancelada",
                        ROLE_RECEPCION,
                        motivo=motivo_invalido,
                    )

                self.assertEqual(raised.exception.code, "VISIT_MOTIVO_REQUERIDO")
                self.assertEqual(raised.exception.status_code, 422)

    def test_cancelar_visita_con_motivo_retorna_target_state(self):
        result = transition_visit_state(
            "en_espera",
            "cancelada",
            ROLE_RECEPCION,
            motivo="El paciente ya no puede asistir.",
        )

        self.assertEqual(result, "cancelada")

    def test_cancelar_nota_cerrada_solo_autorizador_con_motivo(self):
        result = transition_visit_state(
            "cerrada", "cancelada", ROLE_AUTORIZADOR_NOTA, motivo="Nota duplicada",
        )
        self.assertEqual(result, "cancelada")

        # Recepcion (y cualquier otro rol) ya no puede cancelar una nota
        # cerrada: antes era 409 por transicion inexistente, ahora 403.
        for role in (ROLE_RECEPCION, ROLE_DOCTOR, ROLE_SOMATOMETRIA):
            with self.subTest(role=role):
                with self.assertRaises(VisitDomainError) as raised:
                    transition_visit_state("cerrada", "cancelada", role, motivo="x")
                self.assertEqual(raised.exception.code, "ROLE_NOT_ALLOWED")
                self.assertEqual(raised.exception.status_code, 403)

        with self.assertRaises(VisitDomainError) as raised:
            transition_visit_state("cerrada", "cancelada", ROLE_AUTORIZADOR_NOTA, motivo=None)
        self.assertEqual(raised.exception.code, "VISIT_MOTIVO_REQUERIDO")

    def test_transition_matrix_covers_all_official_states(self):
        matrix = get_transition_matrix()

        self.assertEqual(len(matrix), len(VISIT_STATES) * len(VISIT_STATES))

        valid_rows = [row for row in matrix if row["is_valid"]]
        self.assertEqual(len(valid_rows), len(VALID_TRANSITIONS))

        for row in matrix:
            with self.subTest(row=row):
                self.assertIn(row["current_state"], VISIT_STATES)
                self.assertIn(row["target_state"], VISIT_STATES)
                self.assertIn(row["reason"], {"VALID", "VISIT_STATE_INVALID"})
