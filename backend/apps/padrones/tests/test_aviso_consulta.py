"""Crónicos, entrega 1: aviso en consulta y sugerencia de inscripción
(docs/plans/cronicos-aviso-consulta.md)."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.administracion.models import AuditoriaEvento
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies, MotivoBajaPadron
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.padrones.models import ChronicEnrollment, ChronicProgram, ChronicProgramCie
from apps.padrones.uses_case import aviso_consulta_usecase as aviso
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

DOCTOR = ["clinico:consultas:read"]
DOCTOR_ENROLLS = ["clinico:consultas:read", "clinico:padrones:write"]
PADRON_WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
CLASSIFY = "apps.consulta_medica.services.diagnosis_redaction_service.classify_cie"


def _vih_only(code):
    return ("VIH", "clinico:diagnosticos_vih:read") if (code or "").upper().startswith("B2") else None


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="medico_aviso", clave_hash="x")
        cls.center = make_center()
        cls.visit_center = make_center()
        for code, description in [
            ("E11", "DIABETES TIPO 2"), ("E119", "DIABETES TIPO 2 SIN COMPLICACIONES"),
            ("I10", "HIPERTENSION ESENCIAL"), ("J00", "RINOFARINGITIS AGUDA"), ("B24", "VIH"),
        ]:
            CatCies.objects.create(code=code, description=description, version="CIE-10")
        cls.reason = MotivoBajaPadron.objects.get(name="Defunción")
        # B24 en un programa de prueba: sirve para probar que un CIE sensible
        # no se sugiere aunque pertenezca a un programa.
        sensible = ChronicProgram.objects.create(code="TEST_VIH", name="Programa de prueba")
        ChronicProgramCie.objects.create(program=sensible, cie_prefix="B24")

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _visit(self, no_exp="EXP-AV", folio="V-AV-1", center=None):
        return Visit.objects.create(
            folio=folio, patient=paciente_de_llave(no_exp, 0), arrival_type="walk_in",
            service_type="medicina_general", status="en_consulta", nombre_paciente="Paciente Aviso",
            centro=center if center is not None else self.visit_center,
        )

    def _enroll(self, no_exp="EXP-AV", item_id="E11"):
        return uc.enroll("cronicos", no_exp=no_exp, pk_num=0, item_id=item_id, center_id=self.center.pk,
                         actor=self.actor, permissions=PADRON_WRITE)


class ProgramCatalogTests(_Base):
    def test_seeded_programs_cover_the_main_chronic_diseases(self):
        codes = set(ChronicProgram.objects.filter(is_active=True).values_list("code", flat=True))
        self.assertTrue({"DIABETES", "HIPERTENSION", "DISLIPIDEMIA", "OBESIDAD", "ERC"} <= codes)

    def test_match_by_prefix_ignoring_dot_and_case(self):
        self.assertEqual(aviso.program_for_cie("E11").code, "DIABETES")
        self.assertEqual(aviso.program_for_cie("e11.9").code, "DIABETES")
        self.assertEqual(aviso.program_for_cie("E119").code, "DIABETES")
        self.assertEqual(aviso.program_for_cie("I10").code, "HIPERTENSION")
        self.assertIsNone(aviso.program_for_cie("J00"))
        self.assertIsNone(aviso.program_for_cie(""))

    def test_longest_prefix_wins_and_inactive_programs_are_ignored(self):
        specific = ChronicProgram.objects.create(code="DM_COMPLICADA", name="Diabetes complicada")
        ChronicProgramCie.objects.create(program=specific, cie_prefix="E115")
        self.assertEqual(aviso.program_for_cie("E11.5").code, "DM_COMPLICADA")
        self.assertEqual(aviso.program_for_cie("E11.9").code, "DIABETES")
        ChronicProgram.objects.filter(code="DIABETES").update(is_active=False)
        self.assertIsNone(aviso.program_for_cie("E11.9"))


class NoticeTests(_Base):
    def test_lists_only_active_enrollments_of_the_visit_patient_with_program(self):
        visit = self._visit()
        self._enroll()
        discharged = self._enroll(item_id="I10")
        uc.discharge("cronicos", discharged.pk, reason_id=self.reason.pk, actor=self.actor, permissions=PADRON_WRITE)
        self._enroll(no_exp="EXP-OTRO", item_id="I10")

        notice = aviso.get_notice(visit.id_visit, permissions=DOCTOR)

        self.assertEqual([e["item"]["code"] for e in notice["enrollments"]], ["E11"])
        self.assertEqual(notice["enrollments"][0]["program"], {"code": "DIABETES", "name": "Diabetes mellitus"})
        self.assertFalse(notice["canEnroll"])
        self.assertIsNone(notice["suggestion"])

    def test_sensitive_diagnosis_is_redacted(self):
        visit = self._visit()
        self._enroll(item_id="B24")
        with mock.patch(CLASSIFY, side_effect=_vih_only):
            notice = aviso.get_notice(visit.id_visit, permissions=DOCTOR)
        item = notice["enrollments"][0]["item"]
        self.assertTrue(item["restricted"])
        self.assertIsNone(item["code"])
        self.assertNotIn("VIH", item["description"])
        self.assertIsNone(notice["enrollments"][0]["program"])  # el programa delataria el diagnostico

    def test_requires_consultation_or_padron_read(self):
        visit = self._visit()
        with self.assertRaises(VisitDomainError) as ctx:
            aviso.get_notice(visit.id_visit, permissions=["clinico:recetas:imprimir"])
        self.assertEqual(ctx.exception.status_code, 403)
        aviso.get_notice(visit.id_visit, permissions=["clinico:padrones:read"])  # no lanza

    def test_unknown_visit_is_404(self):
        with self.assertRaises(VisitDomainError) as ctx:
            aviso.get_notice(999999, permissions=DOCTOR)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("VISIT_NOT_FOUND", 404))


class SuggestionTests(_Base):
    def test_suggests_program_for_a_chronic_diagnosis(self):
        visit = self._visit()
        notice = aviso.get_notice(visit.id_visit, cie="E11.9", permissions=DOCTOR_ENROLLS)
        self.assertEqual(notice["suggestion"], {
            "cie": {"code": "E119", "description": "DIABETES TIPO 2 SIN COMPLICACIONES"},
            "program": {"code": "DIABETES", "name": "Diabetes mellitus"},
        })
        self.assertTrue(notice["canEnroll"])

    def test_no_suggestion_when_already_in_the_same_program(self):
        visit = self._visit()
        self._enroll(item_id="E11")
        self.assertIsNone(aviso.get_notice(visit.id_visit, cie="E119", permissions=DOCTOR)["suggestion"])
        # Otro programa si se sugiere.
        self.assertEqual(
            aviso.get_notice(visit.id_visit, cie="I10", permissions=DOCTOR)["suggestion"]["program"]["code"],
            "HIPERTENSION",
        )

    def test_no_suggestion_for_non_chronic_unknown_or_sensitive_cie(self):
        visit = self._visit()
        for cie in ("J00", "ZZZ9", ""):
            with self.subTest(cie=cie):
                self.assertIsNone(aviso.get_notice(visit.id_visit, cie=cie, permissions=DOCTOR)["suggestion"])
        with mock.patch(CLASSIFY, side_effect=_vih_only):
            self.assertIsNone(aviso.get_notice(visit.id_visit, cie="B24", permissions=DOCTOR)["suggestion"])

    def test_no_suggestion_for_inactive_cie(self):
        visit = self._visit()
        CatCies.objects.filter(code="I10").update(is_active=False)
        self.assertIsNone(aviso.get_notice(visit.id_visit, cie="I10", permissions=DOCTOR)["suggestion"])


class EnrollFromVisitTests(_Base):
    def test_enrolls_the_visit_patient_in_the_visit_center(self):
        visit = self._visit()
        enrollment = aviso.enroll_from_visit(
            visit.id_visit, item_id="E119", notes=" desde consulta ", actor=self.actor, permissions=DOCTOR_ENROLLS,
        )
        self.assertEqual(enrollment.patient_id, visit.patient_id)
        self.assertEqual(enrollment.center_id, self.visit_center.pk)
        self.assertEqual(enrollment.enrolled_on, timezone.localdate())
        self.assertEqual((enrollment.enrolled_by, enrollment.notes), (self.actor, "desde consulta"))

    def test_falls_back_to_user_center_when_visit_has_none(self):
        visit = self._visit()
        Visit.objects.filter(pk=visit.pk).update(centro=None)
        DetUsuario.objects.create(id_usuario=self.actor, nombre="Med", paterno="Aviso", materno="",
                                  id_centro_atencion=self.center)
        enrollment = aviso.enroll_from_visit(visit.id_visit, item_id="E11", actor=self.actor,
                                             permissions=DOCTOR_ENROLLS)
        self.assertEqual(enrollment.center_id, self.center.pk)

    def test_rules(self):
        visit = self._visit()
        with self.assertRaises(VisitDomainError) as ctx:
            aviso.enroll_from_visit(visit.id_visit, item_id="E11", actor=self.actor, permissions=DOCTOR)
        self.assertEqual(ctx.exception.status_code, 403)

        aviso.enroll_from_visit(visit.id_visit, item_id="E11", actor=self.actor, permissions=DOCTOR_ENROLLS)
        with self.assertRaises(VisitDomainError) as ctx:
            aviso.enroll_from_visit(visit.id_visit, item_id="E11", actor=self.actor, permissions=DOCTOR_ENROLLS)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("ALREADY_ENROLLED", 409))

        with self.assertRaises(VisitDomainError) as ctx:
            aviso.enroll_from_visit(visit.id_visit, item_id="ZZZ", actor=self.actor, permissions=DOCTOR_ENROLLS)
        self.assertIn("itemId", ctx.exception.details)

        with self.assertRaises(VisitDomainError) as ctx:
            aviso.enroll_from_visit(999999, item_id="E11", actor=self.actor, permissions=DOCTOR_ENROLLS)
        self.assertEqual(ctx.exception.status_code, 404)


class NoticeApiTests(_Base):
    def setUp(self):
        super().setUp()
        self.client_api, self.user = _login_client("medico_cronicos", DOCTOR_ENROLLS)
        self.visit = self._visit()

    def test_notice_and_enroll_with_audit(self):
        url = f"/api/v1/padrones/cronicos/visita/{self.visit.id_visit}"
        notice = self.client_api.get(f"{url}/aviso?cie=E11.9")
        self.assertEqual(notice.status_code, 200, notice.content)
        self.assertEqual(notice.data["suggestion"]["program"]["code"], "DIABETES")
        self.assertEqual(notice.data["enrollments"], [])

        created = self.client_api.post(url, {"itemId": "E119"}, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.data["item"]["code"], "E119")
        self.assertEqual(created.data["center"]["id"], self.visit_center.pk)
        event = AuditoriaEvento.objects.get(accion="RegistryEnrollmentCreated")
        self.assertEqual(event.meta.get("source"), "consulta")

        after = self.client_api.get(f"{url}/aviso?cie=E11.9")
        self.assertEqual([e["item"]["code"] for e in after.data["enrollments"]], ["E119"])
        self.assertIsNone(after.data["suggestion"])

    def test_errors(self):
        self.assertEqual(self.client_api.get("/api/v1/padrones/cronicos/visita/999999/aviso").status_code, 404)
        bad = self.client_api.post(f"/api/v1/padrones/cronicos/visita/{self.visit.id_visit}", {}, format="json")
        self.assertEqual(bad.status_code, 422)
        reader, _ = _login_client("solo_lectura_aviso", DOCTOR)
        forbidden = reader.post(
            f"/api/v1/padrones/cronicos/visita/{self.visit.id_visit}", {"itemId": "E11"}, format="json",
        )
        self.assertEqual(forbidden.status_code, 403)
