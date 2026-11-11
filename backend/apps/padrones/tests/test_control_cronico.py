"""Crónicos, entrega 2: control en la consulta con metas y semáforo
(docs/plans/cronicos-control.md)."""
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.administracion.models import AuditoriaEvento
from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, MotivoBajaPadron
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.padrones.domain import control_cronico as rules
from apps.padrones.models import ChronicControl, ChronicControlGoal, ChronicProgram
from apps.padrones.uses_case import control_cronico_usecase as control
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError
from apps.somatometria.models import VisitVitalSigns

DOCTOR = ["clinico:consultas:read"]
CONTROL = ["clinico:consultas:read", "clinico:cronicos:control"]
PADRON_WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
TODAY = timezone.localdate()


class RulesTests(SimpleTestCase):
    def test_in_goal_is_inclusive_and_none_without_value_or_goal(self):
        self.assertTrue(rules.in_goal(Decimal("130"), None, Decimal("130")))
        self.assertFalse(rules.in_goal(Decimal("131"), None, Decimal("130")))
        self.assertTrue(rules.in_goal(Decimal("70"), Decimal("70"), Decimal("130")))
        self.assertFalse(rules.in_goal(Decimal("69"), Decimal("70"), Decimal("130")))
        self.assertIsNone(rules.in_goal(None, None, Decimal("130")))
        self.assertIsNone(rules.in_goal(Decimal("5"), None, None))

    def test_status(self):
        self.assertEqual(rules.control_status([]), "sin_datos")
        self.assertEqual(rules.control_status([None, None]), "sin_datos")
        self.assertEqual(rules.control_status([True, False, None]), "descontrolado")
        self.assertEqual(rules.control_status([True, None]), "incompleto")
        self.assertEqual(rules.control_status([True, True]), "controlado")


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="medico_control", clave_hash="x")
        cls.center = make_center()
        for code, description in [("E11", "DIABETES TIPO 2"), ("I10", "HIPERTENSION"), ("B24", "VIH")]:
            CatCies.objects.create(code=code, description=description, version="CIE-10")
        cls.reason = MotivoBajaPadron.objects.get(name="Defunción")

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _visit(self, folio="V-CTL-1", no_exp="EXP-CTL", status="en_consulta", vitals=None):
        visit = Visit.objects.create(
            folio=folio, patient=paciente_de_llave(no_exp, 0), arrival_type="walk_in",
            service_type="medicina_general", status=status, nombre_paciente="Paciente Control",
            centro=self.center,
        )
        if vitals is not None:
            VisitVitalSigns.objects.create(
                id_visit=visit, patient=visit.patient, weight_kg="80.00", height_cm="170.00", bmi="27.68",
                **vitals,
            )
        return visit

    def _enroll(self, item_id="E11", no_exp="EXP-CTL"):
        return uc.enroll("cronicos", no_exp=no_exp, pk_num=0, item_id=item_id, center_id=self.center.pk,
                         actor=self.actor, permissions=PADRON_WRITE)

    @staticmethod
    def _program(panel, code):
        return next(p for p in panel["programs"] if p["program"]["code"] == code)

    @staticmethod
    def _param(entry, parameter):
        return next(p for p in entry["parameters"] if p["parameter"] == parameter)


class SeededGoalsTests(_Base):
    def test_programs_have_periodicity_and_goals(self):
        diabetes = ChronicProgram.objects.get(code="DIABETES")
        self.assertEqual(diabetes.control_every_days, 90)
        goals = {g.parameter: (g.min_value, g.max_value) for g in ChronicControlGoal.objects.filter(program=diabetes)}
        self.assertEqual(goals["hba1c"], (None, Decimal("7.00")))
        self.assertEqual(goals["glucosa_capilar"], (Decimal("70.00"), Decimal("130.00")))
        self.assertEqual(goals["ta_sistolica"], (None, Decimal("130.00")))
        self.assertEqual(ChronicControlGoal.objects.count(), 12)


class PanelTests(_Base):
    def test_shows_visit_vitals_against_program_goals(self):
        self._enroll()
        visit = self._visit(vitals={"blood_pressure_systolic": 135, "blood_pressure_diastolic": 78,
                                    "glucosa_capilar_mgdl": 110})
        panel = control.get_control_panel(visit.id_visit, permissions=CONTROL)

        self.assertTrue(panel["canRegister"])
        entry = self._program(panel, "DIABETES")
        self.assertEqual(entry["everyDays"], 90)
        sistolica = self._param(entry, "ta_sistolica")
        self.assertEqual((sistolica["value"], sistolica["goalMax"], sistolica["inGoal"]), (135.0, 130.0, False))
        self.assertEqual(sistolica["source"], "somatometria")
        self.assertTrue(self._param(entry, "glucosa_capilar")["inGoal"])
        hba1c = self._param(entry, "hba1c")
        self.assertEqual((hba1c["value"], hba1c["source"], hba1c["inGoal"]), (None, "manual", None))
        cintura = self._param(entry, "cintura")  # informativo, sin meta
        self.assertEqual((cintura["goalMin"], cintura["goalMax"]), (None, None))
        self.assertEqual(entry["status"], "descontrolado")
        self.assertEqual(entry["suggestedNextControlOn"], TODAY + timedelta(days=90))
        self.assertIsNone(entry["registered"])
        self.assertIsNone(entry["last"])

    def test_one_entry_per_program_and_no_vitals_means_no_data(self):
        self._enroll()
        self._enroll(item_id="I10")
        visit = self._visit()
        panel = control.get_control_panel(visit.id_visit, permissions=DOCTOR)
        self.assertEqual({p["program"]["code"] for p in panel["programs"]}, {"DIABETES", "HIPERTENSION"})
        self.assertEqual(self._program(panel, "HIPERTENSION")["status"], "sin_datos")
        self.assertFalse(panel["canRegister"])

    def test_discharged_or_unprogrammed_enrollments_have_no_control(self):
        discharged = self._enroll()
        uc.discharge("cronicos", discharged.pk, reason_id=self.reason.pk, actor=self.actor, permissions=PADRON_WRITE)
        self._enroll(item_id="B24")  # sin programa
        visit = self._visit()
        self.assertEqual(control.get_control_panel(visit.id_visit, permissions=DOCTOR)["programs"], [])

    def test_last_control_and_overdue(self):
        self._enroll()
        old = self._visit(folio="V-CTL-OLD")
        control.register_control(old.id_visit, program_code="DIABETES", values={"hba1c": "8.1"},
                                 actor=self.actor, permissions=CONTROL)
        ChronicControl.objects.update(control_on=TODAY - timedelta(days=120),
                                      next_control_on=TODAY - timedelta(days=30))
        visit = self._visit(folio="V-CTL-NEW")
        last = self._program(control.get_control_panel(visit.id_visit, permissions=DOCTOR), "DIABETES")["last"]
        self.assertEqual(last["status"], "descontrolado")
        self.assertTrue(last["overdue"])
        self.assertEqual(last["controlOn"], TODAY - timedelta(days=120))

    def test_permissions_and_404(self):
        visit = self._visit()
        with self.assertRaises(VisitDomainError) as ctx:
            control.get_control_panel(visit.id_visit, permissions=["clinico:recetas:imprimir"])
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(VisitDomainError) as ctx:
            control.get_control_panel(999999, permissions=DOCTOR)
        self.assertEqual(ctx.exception.status_code, 404)


class RegisterTests(_Base):
    def test_registers_status_measurements_goal_snapshot_and_next_control(self):
        self._enroll()
        visit = self._visit(vitals={"blood_pressure_systolic": 120, "blood_pressure_diastolic": 75,
                                    "glucosa_capilar_mgdl": 100})
        registered = control.register_control(
            visit.id_visit, program_code="DIABETES", values={"hba1c": "6.5"}, adherence="buena",
            notes="  bien  ", actor=self.actor, permissions=CONTROL,
        )
        self.assertEqual(registered.status, "controlado")
        self.assertEqual(registered.next_control_on, TODAY + timedelta(days=90))
        self.assertEqual((registered.center_id, registered.patient_id), (self.center.pk, visit.patient_id))
        self.assertEqual((registered.adherence, registered.notes, registered.registered_by),
                         ("buena", "bien", self.actor))
        hba1c = registered.measurements.get(parameter="hba1c")
        self.assertEqual((hba1c.value, hba1c.source, hba1c.goal_max, hba1c.in_goal),
                         (Decimal("6.50"), "manual", Decimal("7.00"), True))
        sistolica = registered.measurements.get(parameter="ta_sistolica")
        self.assertEqual((sistolica.value, sistolica.source), (Decimal("120.00"), "somatometria"))

        # La meta copiada no cambia si despues se ajusta el catalogo.
        ChronicControlGoal.objects.filter(program__code="DIABETES", parameter="hba1c").update(max_value=Decimal("6"))
        hba1c.refresh_from_db()
        self.assertEqual(hba1c.goal_max, Decimal("7.00"))

        panel = control.get_control_panel(visit.id_visit, permissions=CONTROL)
        self.assertEqual(self._program(panel, "DIABETES")["registered"]["status"], "controlado")

    def test_missing_manual_value_leaves_control_incomplete(self):
        self._enroll()
        visit = self._visit(vitals={"blood_pressure_systolic": 120, "blood_pressure_diastolic": 75,
                                    "glucosa_capilar_mgdl": 100})
        registered = control.register_control(visit.id_visit, program_code="DIABETES", values={},
                                               actor=self.actor, permissions=CONTROL)
        self.assertEqual(registered.status, "incompleto")
        self.assertFalse(registered.measurements.filter(parameter="hba1c").exists())

    def test_rules(self):
        self._enroll()
        visit = self._visit()
        cases = [
            (dict(permissions=DOCTOR), 403, "ROLE_NOT_ALLOWED"),
            (dict(program_code="HIPERTENSION"), 422, "VALIDATION_ERROR"),  # no inscrito
            (dict(program_code="NOEXISTE"), 422, "VALIDATION_ERROR"),
            (dict(values={"ta_sistolica": "120"}), 422, "VALIDATION_ERROR"),  # sale de somatometria
            (dict(values={"ldl": "100"}), 422, "VALIDATION_ERROR"),  # sin meta en el programa
            (dict(values={"hba1c": "abc"}), 422, "VALIDATION_ERROR"),
            (dict(values={"hba1c": "0"}), 422, "VALIDATION_ERROR"),
            (dict(values={"hba1c": "1001"}), 422, "VALIDATION_ERROR"),
            (dict(adherence="excelente"), 422, "VALIDATION_ERROR"),
        ]
        for overrides, status, code in cases:
            data = dict(program_code="DIABETES", values={}, actor=self.actor, permissions=CONTROL)
            data.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(VisitDomainError) as ctx:
                control.register_control(visit.id_visit, **data)
            self.assertEqual((ctx.exception.status_code, ctx.exception.code), (status, code))

    def test_once_per_program_and_visit_and_only_in_consultation(self):
        self._enroll()
        visit = self._visit()
        control.register_control(visit.id_visit, program_code="DIABETES", values={}, actor=self.actor,
                                 permissions=CONTROL)
        with self.assertRaises(VisitDomainError) as ctx:
            control.register_control(visit.id_visit, program_code="DIABETES", values={}, actor=self.actor,
                                     permissions=CONTROL)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("CONTROL_ALREADY_REGISTERED", 409))

        closed = self._visit(folio="V-CTL-CERR", status="cerrada")
        with self.assertRaises(VisitDomainError) as ctx:
            control.register_control(closed.id_visit, program_code="DIABETES", values={}, actor=self.actor,
                                     permissions=CONTROL)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("VISIT_NOT_IN_CONSULTATION", 409))


class ControlApiTests(_Base):
    def setUp(self):
        super().setUp()
        self.client_api, self.user = _login_client("medico_control_api", CONTROL)

    def test_panel_and_register_with_audit(self):
        self._enroll()
        visit = self._visit(vitals={"blood_pressure_systolic": 150, "blood_pressure_diastolic": 95})
        url = f"/api/v1/padrones/cronicos/visita/{visit.id_visit}/control"

        panel = self.client_api.get(url)
        self.assertEqual(panel.status_code, 200, panel.content)
        self.assertEqual(panel.data["programs"][0]["program"]["code"], "DIABETES")

        created = self.client_api.post(
            url, {"programCode": "DIABETES", "values": {"hba1c": 9.4}, "adherence": "regular"}, format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.data["status"], "descontrolado")
        self.assertEqual(created.data["nextControlOn"], TODAY + timedelta(days=90))
        hba1c = next(m for m in created.data["measurements"] if m["parameter"] == "hba1c")
        self.assertEqual((hba1c["value"], hba1c["inGoal"]), (9.4, False))
        event = AuditoriaEvento.objects.get(accion="ChronicControlRegistered")
        self.assertEqual(event.datos_despues["status"], "descontrolado")

        again = self.client_api.post(url, {"programCode": "DIABETES"}, format="json")
        self.assertEqual((again.status_code, again.data["code"]), (409, "CONTROL_ALREADY_REGISTERED"))

    def test_validation(self):
        visit = self._visit()
        url = f"/api/v1/padrones/cronicos/visita/{visit.id_visit}/control"
        self.assertEqual(self.client_api.post(url, {}, format="json").status_code, 422)
        self.assertEqual(self.client_api.get("/api/v1/padrones/cronicos/visita/999999/control").status_code, 404)
