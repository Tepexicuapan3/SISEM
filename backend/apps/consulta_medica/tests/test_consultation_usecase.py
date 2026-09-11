from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies
from apps.consulta_medica.models import VisitConsultation, VisitConsultationRevision
from apps.consulta_medica.uses_case.consultation_usecase import (
    close_consultation,
    save_diagnosis,
    save_prescriptions,
    search_cies,
    start_consultation,
)
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError


class ConsultationUseCaseTests(TestCase):
    def setUp(self):
        # doctor_id ahora es FK real a SyUsuario (ver 0006_doctor_fk_integrity) --
        # ya no acepta cualquier entero suelto, hace falta un usuario real.
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_test_1", correo="doctor1@example.com", clave_hash="x",
        ).id_usuario
        self.doctor_id_2 = SyUsuario.objects.create(
            usuario="doctor_test_2", correo="doctor2@example.com", clave_hash="x",
        ).id_usuario
        # cieCode es obligatorio para cerrar una consulta (NOM-024) --
        # fixture compartida para los tests de close_consultation.
        self.cie_code = "I10"
        CatCies.objects.create(
            code=self.cie_code,
            description="HIPERTENSION ESENCIAL (PRIMARIA)",
            version="CIE-10",
            is_active=True,
        )

    def _visit(self, status):
        return Visit.objects.create(
            folio=f"CNS-{status}-{Visit.objects.count() + 1}",
            no_exp=f"EXP{5000 + Visit.objects.count() + 1}",
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-{Visit.objects.count() + 1}",
            status=status,
        )

    def test_start_consultation_happy_path(self):
        visit = self._visit("lista_para_doctor")

        payload = start_consultation(visit.id_visit, ["doctor"])

        self.assertEqual(payload["id"], visit.id_visit)
        self.assertEqual(payload["status"], "en_consulta")
        visit.refresh_from_db()
        self.assertEqual(visit.status, "en_consulta")

    def test_start_consultation_role_not_allowed(self):
        visit = self._visit("lista_para_doctor")

        with self.assertRaises(VisitDomainError) as raised:
            start_consultation(visit.id_visit, ["recepcion"])

        self.assertEqual(raised.exception.code, "ROLE_NOT_ALLOWED")
        self.assertEqual(raised.exception.status_code, 403)

    def test_start_consultation_allows_clinico_permission_dependency(self):
        visit = self._visit("lista_para_doctor")

        payload = start_consultation(
            visit.id_visit,
            ["CLINICO"],
            ["clinico:consultas:read"],
        )

        self.assertEqual(payload["status"], "en_consulta")

    def test_start_consultation_invalid_transition(self):
        visit = self._visit("en_espera")

        with self.assertRaises(VisitDomainError) as raised:
            start_consultation(visit.id_visit, ["DOCTOR"])

        self.assertEqual(raised.exception.code, "VISIT_STATE_INVALID")
        self.assertEqual(raised.exception.status_code, 409)

    def test_close_consultation_happy_path_and_persists_record(self):
        visit = self._visit("en_consulta")

        payload = close_consultation(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Hipertension arterial",
            final_note="Paciente estable y con tratamiento inicial.",
            doctor_id=self.doctor_id,
            cie_code=self.cie_code,
        )

        self.assertEqual(payload["visit"]["status"], "cerrada")
        self.assertEqual(payload["consultation"]["visitId"], visit.id_visit)
        self.assertEqual(payload["consultation"]["doctorId"], self.doctor_id)
        self.assertEqual(payload["consultation"]["primaryDiagnosis"], "Hipertension arterial")

        visit.refresh_from_db()
        self.assertEqual(visit.status, "cerrada")

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(consultation.final_note, "Paciente estable y con tratamiento inicial.")

    def test_close_consultation_allows_clinico_permission_dependency(self):
        visit = self._visit("en_consulta")

        payload = close_consultation(
            visit_id=visit.id_visit,
            roles=["CLINICO"],
            primary_diagnosis="Cefalea tensional",
            final_note="Paciente con manejo sintomatico.",
            doctor_id=self.doctor_id,
            permissions=["clinico:consultas:read"],
            cie_code=self.cie_code,
        )

        self.assertEqual(payload["visit"]["status"], "cerrada")

    def test_close_consultation_requires_required_fields_by_guard_clause(self):
        visit = self._visit("en_consulta")

        with self.assertRaises(VisitDomainError) as raised:
            close_consultation(
                visit_id=visit.id_visit,
                roles=["DOCTOR"],
                primary_diagnosis="  ",
                final_note="",
                doctor_id=self.doctor_id,
                cie_code=self.cie_code,
            )

        self.assertEqual(raised.exception.code, "VISIT_STATE_INVALID")
        self.assertEqual(raised.exception.status_code, 409)

    def test_close_consultation_requires_cie_code(self):
        visit = self._visit("en_consulta")

        with self.assertRaises(VisitDomainError) as raised:
            close_consultation(
                visit_id=visit.id_visit,
                roles=["DOCTOR"],
                primary_diagnosis="Dx",
                final_note="Nota",
                doctor_id=self.doctor_id,
            )

        self.assertEqual(raised.exception.code, "VALIDATION_ERROR")
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("cieCode", raised.exception.details)

    def test_close_consultation_upserts_same_visit_record(self):
        visit = self._visit("en_consulta")
        close_consultation(
            visit.id_visit,
            ["DOCTOR"],
            "Dx inicial",
            "Nota inicial",
            self.doctor_id,
            cie_code=self.cie_code,
        )

        visit.status = "en_consulta"
        visit.save(update_fields=["status", "fch_modf"])

        close_consultation(
            visit.id_visit,
            ["DOCTOR"],
            "Dx final",
            "Nota final",
            self.doctor_id_2,
            cie_code=self.cie_code,
        )

        self.assertEqual(VisitConsultation.objects.filter(id_visit=visit).count(), 1)
        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(consultation.doctor_id, self.doctor_id_2)
        self.assertEqual(consultation.primary_diagnosis, "Dx final")

    def test_save_diagnosis_happy_path_persists_without_closing_visit(self):
        visit = self._visit("en_consulta")

        payload = save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Faringitis aguda",
            final_note="Paciente estable.",
            doctor_id=self.doctor_id,
        )

        self.assertEqual(payload["visitId"], visit.id_visit)
        self.assertEqual(payload["status"], "en_consulta")
        self.assertEqual(payload["primaryDiagnosis"], "Faringitis aguda")
        self.assertIsNone(payload["cieCode"])

        visit.refresh_from_db()
        self.assertEqual(visit.status, "en_consulta")

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(consultation.primary_diagnosis, "Faringitis aguda")
        self.assertEqual(consultation.final_note, "Paciente estable.")

    def test_save_diagnosis_with_cie_code_persists_selection(self):
        visit = self._visit("en_consulta")
        CatCies.objects.create(
            code="A090",
            description="GASTROENTERITIS",
            version="CIE-10",
            is_active=True,
        )

        payload = save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Gastroenteritis aguda",
            final_note="Paciente estable.",
            doctor_id=self.doctor_id,
            cie_code="a090",
        )

        self.assertEqual(payload["cieCode"], "A090")

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(consultation.cie_id, "A090")

    def test_save_diagnosis_twice_with_different_values_creates_revision(self):
        visit = self._visit("en_consulta")

        save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Dx borrador",
            final_note="Nota borrador",
            doctor_id=self.doctor_id,
        )

        save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Dx corregido",
            final_note="Nota corregida",
            doctor_id=self.doctor_id,
            cie_code=self.cie_code,
        )

        consultation = VisitConsultation.objects.get(id_visit=visit)
        # El valor actual es el ultimo -- pero el anterior no se pierde,
        # queda versionado en vez de pisado in-place (NOM-024).
        self.assertEqual(consultation.primary_diagnosis, "Dx corregido")

        revisions = VisitConsultationRevision.objects.filter(consultation=consultation)
        self.assertEqual(revisions.count(), 1)
        revision = revisions.first()
        self.assertEqual(revision.previous_primary_diagnosis, "Dx borrador")
        self.assertEqual(revision.previous_final_note, "Nota borrador")
        self.assertIsNone(revision.previous_cie_id)

    def test_save_diagnosis_twice_with_identical_values_does_not_create_revision(self):
        visit = self._visit("en_consulta")

        for _ in range(2):
            save_diagnosis(
                visit_id=visit.id_visit,
                roles=["DOCTOR"],
                primary_diagnosis="Dx estable",
                final_note="Nota estable",
                doctor_id=self.doctor_id,
            )

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(
            VisitConsultationRevision.objects.filter(consultation=consultation).count(),
            0,
        )

    def test_save_diagnosis_without_soap_fields_leaves_them_null(self):
        visit = self._visit("en_consulta")

        payload = save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Faringitis aguda",
            final_note="Paciente estable.",
            doctor_id=self.doctor_id,
        )

        self.assertIsNone(payload["subjective"])
        self.assertIsNone(payload["objective"])
        self.assertIsNone(payload["assessment"])
        self.assertIsNone(payload["plan"])
        self.assertEqual(payload["finalNote"], "Paciente estable.")

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertIsNone(consultation.subjective)
        self.assertIsNone(consultation.objective)
        self.assertIsNone(consultation.assessment)
        self.assertIsNone(consultation.plan)
        self.assertEqual(consultation.final_note, "Paciente estable.")

    def test_save_diagnosis_with_soap_fields_persists_them(self):
        visit = self._visit("en_consulta")

        payload = save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Faringitis aguda",
            final_note="Paciente estable.",
            doctor_id=self.doctor_id,
            subjective="Refiere dolor de garganta de 3 dias.",
            objective="Faringe eritematosa, sin exudado.",
            assessment="Faringitis aguda viral.",
            plan="Manejo sintomatico, abundantes liquidos.",
        )

        self.assertEqual(payload["subjective"], "Refiere dolor de garganta de 3 dias.")
        self.assertEqual(payload["objective"], "Faringe eritematosa, sin exudado.")
        self.assertEqual(payload["assessment"], "Faringitis aguda viral.")
        self.assertEqual(payload["plan"], "Manejo sintomatico, abundantes liquidos.")
        self.assertEqual(payload["finalNote"], "Paciente estable.")

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(consultation.subjective, "Refiere dolor de garganta de 3 dias.")
        self.assertEqual(consultation.objective, "Faringe eritematosa, sin exudado.")
        self.assertEqual(consultation.assessment, "Faringitis aguda viral.")
        self.assertEqual(consultation.plan, "Manejo sintomatico, abundantes liquidos.")
        self.assertEqual(consultation.final_note, "Paciente estable.")

    def test_save_diagnosis_editing_soap_fields_creates_revision_with_snapshot(self):
        visit = self._visit("en_consulta")

        save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Dx borrador",
            final_note="Nota borrador",
            doctor_id=self.doctor_id,
            subjective="Subjetivo inicial",
            objective="Objetivo inicial",
            assessment="Analisis inicial",
            plan="Plan inicial",
        )

        save_diagnosis(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Dx borrador",
            final_note="Nota borrador",
            doctor_id=self.doctor_id,
            subjective="Subjetivo corregido",
            objective="Objetivo inicial",
            assessment="Analisis inicial",
            plan="Plan inicial",
        )

        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual(consultation.subjective, "Subjetivo corregido")
        self.assertEqual(consultation.final_note, "Nota borrador")

        revisions = VisitConsultationRevision.objects.filter(consultation=consultation)
        self.assertEqual(revisions.count(), 1)
        revision = revisions.first()
        self.assertEqual(revision.previous_subjective, "Subjetivo inicial")
        self.assertEqual(revision.previous_objective, "Objetivo inicial")
        self.assertEqual(revision.previous_assessment, "Analisis inicial")
        self.assertEqual(revision.previous_plan, "Plan inicial")
        self.assertEqual(revision.previous_final_note, "Nota borrador")

    def test_save_diagnosis_invalid_cie_code_raises_validation_error(self):
        visit = self._visit("en_consulta")

        with self.assertRaises(VisitDomainError) as raised:
            save_diagnosis(
                visit_id=visit.id_visit,
                roles=["DOCTOR"],
                primary_diagnosis="Dx",
                final_note="Nota",
                doctor_id=self.doctor_id,
                cie_code="ZZ999",
            )

        self.assertEqual(raised.exception.code, "VALIDATION_ERROR")
        self.assertEqual(raised.exception.status_code, 422)

    def test_search_cies_matches_code_without_special_characters(self):
        CatCies.objects.create(
            code="1A33.0",
            description="CISTOISOSPORIASIS DEL INTESTINO DELGADO",
            version="CIE-10",
            is_active=True,
        )

        payload = search_cies("1A330", roles=["DOCTOR"])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["code"], "1A33.0")

    def test_save_diagnosis_invalid_state_raises_visit_state_invalid(self):
        visit = self._visit("lista_para_doctor")

        with self.assertRaises(VisitDomainError) as raised:
            save_diagnosis(
                visit_id=visit.id_visit,
                roles=["DOCTOR"],
                primary_diagnosis="Dx",
                final_note="Nota",
                doctor_id=self.doctor_id,
            )

        self.assertEqual(raised.exception.code, "VISIT_STATE_INVALID")
        self.assertEqual(raised.exception.status_code, 409)

    def test_save_prescriptions_happy_path(self):
        visit = self._visit("en_consulta")

        payload = save_prescriptions(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            items=["Paracetamol 500mg", "Reposo domiciliario"],
            doctor_id=self.doctor_id,
        )

        self.assertEqual(payload["visitId"], visit.id_visit)
        self.assertEqual(payload["status"], "en_consulta")
        self.assertEqual(
            payload["items"],
            ["Paracetamol 500mg", "Reposo domiciliario"],
        )

    def test_close_consultation_is_idempotent_for_same_payload(self):
        visit = self._visit("en_consulta")

        first_payload = close_consultation(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Dx estable",
            final_note="Nota estable",
            doctor_id=self.doctor_id,
            cie_code=self.cie_code,
        )

        second_payload = close_consultation(
            visit_id=visit.id_visit,
            roles=["DOCTOR"],
            primary_diagnosis="Dx estable",
            final_note="Nota estable",
            doctor_id=self.doctor_id,
            cie_code=self.cie_code,
        )

        self.assertEqual(first_payload["visit"]["status"], "cerrada")
        self.assertEqual(second_payload["visit"]["status"], "cerrada")
        self.assertEqual(
            second_payload["consultation"]["primaryDiagnosis"],
            "Dx estable",
        )
