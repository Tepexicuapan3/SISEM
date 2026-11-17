"""Crónicos, entrega 4: el padrón como lista de trabajo
(docs/plans/cronicos-gestion-padron.md)."""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.consulta_medica.models import Patient
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.padrones.models import ChronicControl
from apps.padrones.uses_case import control_cronico_usecase as control
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

READ = ["clinico:padrones:read"]
WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
CONTROL = ["clinico:consultas:read", "clinico:cronicos:control"]
TODAY = timezone.localdate()


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="gestion_padron", clave_hash="x")
        cls.center = make_center()
        for code, description in [("E11", "DIABETES TIPO 2"), ("I10", "HIPERTENSION"), ("J45", "ASMA")]:
            CatCies.objects.get_or_create(code=code, defaults={"description": description, "version": "CIE-10"})

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _enroll(self, no_exp, item_id="E11", name=None):
        enrollment = uc.enroll("cronicos", no_exp=no_exp, pk_num=0, item_id=item_id, center_id=self.center.pk,
                               actor=self.actor, permissions=WRITE)
        if name:
            first, paternal, maternal = name
            Patient.objects.filter(pk=enrollment.patient_id).update(
                first_name=first, paternal_surname=paternal, maternal_surname=maternal,
            )
        return enrollment

    def _visit(self, no_exp, folio, status="en_consulta"):
        return Visit.objects.create(
            folio=folio, patient=paciente_de_llave(no_exp, 0), arrival_type="walk_in",
            service_type="medicina_general", status=status, nombre_paciente="Paciente Gestion",
            centro=self.center,
        )

    def _control(self, no_exp, folio, *, next_in_days, program="DIABETES"):
        visit = self._visit(no_exp, folio)
        registered = control.register_control(visit.id_visit, program_code=program, actor=self.actor,
                                              permissions=CONTROL)
        ChronicControl.objects.filter(pk=registered.pk).update(next_control_on=TODAY + timedelta(days=next_in_days))
        return registered

    @staticmethod
    def _exps(payload):
        return sorted(item["noExp"] for item in payload["items"])

    def _list(self, **kw):
        return uc.list_enrollments("cronicos", permissions=READ, **kw)


class ContractTests(_Base):
    def test_program_and_last_control_in_each_row(self):
        self._enroll("EXP-G1")
        self._enroll("EXP-G2", item_id="J45")
        self._control("EXP-G1", "V-G1", next_in_days=-5)
        rows = {item["noExp"]: item for item in self._list()["items"]}

        self.assertEqual(rows["EXP-G1"]["program"], {"code": "DIABETES", "name": "Diabetes mellitus"})
        last = rows["EXP-G1"]["lastControl"]
        self.assertEqual((last["controlOn"], last["status"], last["overdue"]), (TODAY, "sin_datos", True))
        self.assertEqual(last["nextControlOn"], TODAY - timedelta(days=5))
        self.assertIsNone(rows["EXP-G2"]["program"])
        self.assertIsNone(rows["EXP-G2"]["lastControl"])

    def test_last_control_is_the_latest_of_that_program(self):
        self._enroll("EXP-G3")
        self._enroll("EXP-G3", item_id="I10")
        self._control("EXP-G3", "V-G3A", next_in_days=-10)
        self._control("EXP-G3", "V-G3B", next_in_days=30)
        rows = {item["item"]["code"]: item for item in self._list()["items"]}
        self.assertFalse(rows["E11"]["lastControl"]["overdue"])
        self.assertIsNone(rows["I10"]["lastControl"])  # el control fue de Diabetes, no de Hipertension

    def test_without_new_filters_the_list_is_unchanged(self):
        for no_exp in ("EXP-G4", "EXP-G5"):
            self._enroll(no_exp)
        self.assertEqual(self._list()["total"], 2)


class FilterTests(_Base):
    def setUp(self):
        super().setUp()
        self._enroll("EXP-VENC", name=("JUAN", "PEREZ", "LOPEZ"))
        self._enroll("EXP-ALDIA", name=("MARIA", "RUIZ", "SOTO"))
        self._enroll("EXP-SIN", name=("JUANA", "PEREZ", "DIAZ"))
        self._enroll("EXP-HTA", item_id="I10")
        self._enroll("EXP-ASMA", item_id="J45")
        self._control("EXP-VENC", "V-VENC", next_in_days=-1)
        self._control("EXP-ALDIA", "V-ALDIA", next_in_days=0)

    def test_by_program(self):
        self.assertEqual(self._exps(self._list(program="diabetes")), ["EXP-ALDIA", "EXP-SIN", "EXP-VENC"])
        self.assertEqual(self._exps(self._list(program="HIPERTENSION")), ["EXP-HTA"])

    def test_by_control_situation(self):
        self.assertEqual(self._exps(self._list(control="vencido")), ["EXP-VENC"])
        self.assertEqual(self._exps(self._list(control="al_dia")), ["EXP-ALDIA"])
        # Sin programa (asma) no cuenta como "sin control".
        self.assertEqual(self._exps(self._list(control="sin_control")), ["EXP-HTA", "EXP-SIN"])

    def test_by_name_all_words(self):
        self.assertEqual(self._exps(self._list(search="perez")), ["EXP-SIN", "EXP-VENC"])
        self.assertEqual(self._exps(self._list(search="  juan  lopez ")), ["EXP-VENC"])

    def test_combined_and_invalid(self):
        self.assertEqual(self._exps(self._list(program="DIABETES", control="sin_control")), ["EXP-SIN"])
        for kw, field in [({"program": "NOEXISTE"}, "program"), ({"control": "otro"}, "control")]:
            with self.assertRaises(VisitDomainError) as ctx:
                self._list(**kw)
            self.assertIn(field, ctx.exception.details)

    def test_program_and_control_only_in_chronic_registry(self):
        with self.assertRaises(VisitDomainError) as ctx:
            uc.list_enrollments("discapacidad", permissions=READ, control="vencido")
        self.assertEqual(ctx.exception.status_code, 422)


class ProgramsCatalogTests(_Base):
    def test_active_programs(self):
        programs = uc.list_programs(permissions=READ)["items"]
        self.assertIn({"code": "DIABETES", "name": "Diabetes mellitus"}, programs)
        self.assertEqual(len(programs), 5)
        with self.assertRaises(VisitDomainError) as ctx:
            uc.list_programs(permissions=["clinico:consultas:read"])
        self.assertEqual(ctx.exception.status_code, 403)


class PanelVisitStatusTests(_Base):
    def test_panel_says_if_the_visit_is_in_consultation(self):
        self._enroll("EXP-PNL")
        waiting = self._visit("EXP-PNL", "V-PNL-1", status="en_espera")
        self.assertFalse(control.get_control_panel(waiting.id_visit, permissions=CONTROL)["visitInConsultation"])
        Visit.objects.filter(pk=waiting.pk).update(status="en_consulta")
        self.assertTrue(control.get_control_panel(waiting.id_visit, permissions=CONTROL)["visitInConsultation"])


class ApiTests(_Base):
    def setUp(self):
        super().setUp()
        self.client_api, _ = _login_client("lector_gestion", READ)

    def test_list_filters_and_programs_endpoint(self):
        self._enroll("EXP-API")
        self._enroll("EXP-API2", item_id="J45")
        response = self.client_api.get("/api/v1/padrones/cronicos?program=DIABETES&control=sin_control")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([i["noExp"] for i in response.data["items"]], ["EXP-API"])
        self.assertEqual(self.client_api.get("/api/v1/padrones/cronicos?control=x").status_code, 422)

        programs = self.client_api.get("/api/v1/padrones/cronicos/programas")
        self.assertEqual(programs.status_code, 200, programs.content)
        self.assertEqual(len(programs.data["items"]), 5)
