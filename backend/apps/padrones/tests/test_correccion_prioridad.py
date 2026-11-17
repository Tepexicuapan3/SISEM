"""Padrones, entrega 5: corregir una inscripcion y ordenar por prioridad
(docs/plans/padrones-correccion-y-prioridad.md)."""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.administracion.models import AuditoriaEvento
from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Discapacidades, MotivoBajaPadron
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.padrones.models import ChronicControl, ChronicEnrollment, EnrollmentSource, RegistryStatus
from apps.padrones.uses_case import control_cronico_usecase as control
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

READ = ["clinico:padrones:read"]
WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
CONTROL = ["clinico:consultas:read", "clinico:cronicos:control"]
CLASSIFY = "apps.consulta_medica.services.diagnosis_redaction_service.classify_cie"
TODAY = timezone.localdate()


def _vih_only(code):
    return ("VIH", "clinico:diagnosticos_vih:read") if (code or "").upper().startswith("B2") else None


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="correccion_padron", clave_hash="x")
        cls.center = make_center()
        for code, description in [("E11", "DIABETES TIPO 2"), ("E10", "DIABETES TIPO 1"),
                                  ("I10", "HIPERTENSION"), ("J45", "ASMA"), ("B24", "VIH")]:
            CatCies.objects.get_or_create(code=code, defaults={"description": description, "version": "CIE-10"})
        cls.disability = Discapacidades.objects.create(code="B1", name="FUNCIONES MENTALES")

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _enroll(self, no_exp, item_id="E11", kind="cronicos", **kw):
        return uc.enroll(kind, no_exp=no_exp, pk_num=0, item_id=item_id, center_id=self.center.pk,
                         actor=self.actor, permissions=WRITE, **kw)

    def _correct(self, enrollment, kind="cronicos", **kw):
        data = dict(detail="Se capturó otro CIE", actor=self.actor, permissions=WRITE)
        data.update(kw)
        return uc.correct(kind, enrollment.pk, **data)


class CorrectionTests(_Base):
    def test_correcting_the_cie_discharges_the_original_and_creates_the_new_one(self):
        original = self._enroll("EXP-C1", enrolled_on=TODAY - timedelta(days=30), notes="Referido")
        discharged, created = self._correct(original, item_id="E10")

        self.assertEqual(discharged.pk, original.pk)
        self.assertEqual(discharged.status, RegistryStatus.BAJA)
        self.assertEqual(discharged.discharge_reason.name, "Registro erróneo")
        self.assertEqual(discharged.discharged_on, TODAY)
        self.assertEqual(discharged.discharge_detail, f"Corregida por la inscripción #{created.pk}: Se capturó otro CIE")

        self.assertEqual(created.status, RegistryStatus.ACTIVO)
        self.assertEqual(created.cie_id, "E10")
        # Conserva paciente, centro, fecha, observaciones y origen.
        self.assertEqual((created.patient_id, created.center_id), (original.patient_id, original.center_id))
        self.assertEqual((created.enrolled_on, created.notes), (TODAY - timedelta(days=30), "Referido"))
        self.assertEqual(created.source, EnrollmentSource.MANUAL)
        self.assertEqual(created.enrolled_by, self.actor)

    def test_can_correct_only_the_date_or_the_notes(self):
        by_date = self._enroll("EXP-C2")
        _, created = self._correct(by_date, enrolled_on=TODAY - timedelta(days=3))
        self.assertEqual((created.cie_id, created.enrolled_on), ("E11", TODAY - timedelta(days=3)))

        by_notes = self._enroll("EXP-C3", notes="Viejo")
        _, created = self._correct(by_notes, notes="")
        self.assertIsNone(created.notes)

    def test_without_changes_is_rejected(self):
        original = self._enroll("EXP-C4", notes="Igual")
        with self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="E11", enrolled_on=original.enrolled_on, notes="Igual")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ChronicEnrollment.objects.get(pk=original.pk).status, RegistryStatus.ACTIVO)

    def test_detail_is_required(self):
        original = self._enroll("EXP-C5")
        with self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="E10", detail="  ")
        self.assertEqual((ctx.exception.status_code, list(ctx.exception.details)), (422, ["detail"]))

    def test_discharged_enrollment_cannot_be_corrected(self):
        original = self._enroll("EXP-C6")
        self._correct(original, item_id="E10")
        with self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="I10")
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("ENROLLMENT_ALREADY_DISCHARGED", 409))

    def test_duplicate_active_cie_rolls_back_the_discharge(self):
        original = self._enroll("EXP-C7")
        self._enroll("EXP-C7", item_id="I10")
        with self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="I10")
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("ALREADY_ENROLLED", 409))
        self.assertEqual(ChronicEnrollment.objects.get(pk=original.pk).status, RegistryStatus.ACTIVO)

    def test_validations_of_the_new_data(self):
        original = self._enroll("EXP-C8")
        cases = [
            (dict(item_id="ZZZ"), "itemId"),
            (dict(enrolled_on=TODAY + timedelta(days=1)), "enrolledOn"),
        ]
        for kwargs, field in cases:
            with self.subTest(field=field), self.assertRaises(VisitDomainError) as ctx:
                self._correct(original, **kwargs)
            self.assertIn(field, ctx.exception.details)

    def test_restricted_diagnosis_cannot_be_corrected_without_permission(self):
        original = self._enroll("EXP-C9", item_id="B24")
        with mock.patch(CLASSIFY, side_effect=_vih_only), self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="E11", roles=[])
        self.assertEqual(ctx.exception.status_code, 403)

    def test_missing_reason_in_catalog(self):
        original = self._enroll("EXP-C10")
        MotivoBajaPadron.objects.filter(name="Registro erróneo").update(is_active=False)
        with self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="E10")
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("CORRECTION_REASON_MISSING", 409))

    def test_requires_write_permission(self):
        original = self._enroll("EXP-C11")
        with self.assertRaises(VisitDomainError) as ctx:
            self._correct(original, item_id="E10", permissions=READ)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_disability_correction(self):
        other = Discapacidades.objects.create(code="B2", name="FUNCIONES SENSORIALES")
        original = self._enroll("EXP-C12", kind="discapacidad", item_id=str(self.disability.pk))
        _, created = self._correct(original, kind="discapacidad", item_id=str(other.pk))
        self.assertEqual(created.disability_id, other.pk)


class CorrectionApiTests(_Base):
    def setUp(self):
        super().setUp()
        self.client_api, self.user = _login_client("correccion_api", WRITE)

    def test_correction_endpoint_returns_the_new_enrollment_with_audit(self):
        original = self._enroll("EXP-CA1")
        response = self.client_api.post(
            f"/api/v1/padrones/cronicos/{original.pk}/correccion",
            {"itemId": "E10", "detail": "CIE equivocado"}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["item"]["code"], "E10")
        self.assertNotEqual(response.data["id"], original.pk)

        event = AuditoriaEvento.objects.get(accion="RegistryEnrollmentCorrected")
        self.assertEqual(event.recurso_id, original.pk)
        self.assertEqual(event.datos_despues["newEnrollmentId"], response.data["id"])

    def test_detail_is_required_by_the_endpoint(self):
        original = self._enroll("EXP-CA2")
        response = self.client_api.post(
            f"/api/v1/padrones/cronicos/{original.pk}/correccion", {"itemId": "E10"}, format="json",
        )
        self.assertEqual(response.status_code, 422)


class PriorityOrderTests(_Base):
    def _visit(self, no_exp, folio):
        return Visit.objects.create(
            folio=folio, patient=paciente_de_llave(no_exp, 0), arrival_type="walk_in",
            service_type="medicina_general", status="en_consulta", nombre_paciente="Paciente Orden",
            centro=self.center,
        )

    def _control(self, no_exp, folio, *, next_in_days):
        visit = self._visit(no_exp, folio)
        registered = control.register_control(visit.id_visit, program_code="DIABETES", actor=self.actor,
                                              permissions=CONTROL)
        ChronicControl.objects.filter(pk=registered.pk).update(next_control_on=TODAY + timedelta(days=next_in_days))

    def test_overdue_first_then_without_control_then_up_to_date_then_without_program(self):
        self._enroll("EXP-ASMA", item_id="J45")
        self._enroll("EXP-ALDIA")
        self._enroll("EXP-SIN")
        self._enroll("EXP-VENC-1")
        self._enroll("EXP-VENC-30")
        self._control("EXP-ALDIA", "V-O1", next_in_days=10)
        self._control("EXP-VENC-1", "V-O2", next_in_days=-1)
        self._control("EXP-VENC-30", "V-O3", next_in_days=-30)

        payload = uc.list_enrollments("cronicos", permissions=READ, order="prioridad")
        self.assertEqual(
            [item["noExp"] for item in payload["items"]],
            ["EXP-VENC-30", "EXP-VENC-1", "EXP-SIN", "EXP-ALDIA", "EXP-ASMA"],
        )

    def test_without_order_the_list_keeps_the_enrollment_order(self):
        self._enroll("EXP-PRIMERO", enrolled_on=TODAY - timedelta(days=5))
        self._enroll("EXP-ULTIMO")
        payload = uc.list_enrollments("cronicos", permissions=READ)
        self.assertEqual([item["noExp"] for item in payload["items"]], ["EXP-ULTIMO", "EXP-PRIMERO"])

    def test_priority_order_only_applies_to_chronic_and_known_values(self):
        for kind, order in (("discapacidad", "prioridad"), ("cronicos", "otro")):
            with self.subTest(kind=kind, order=order), self.assertRaises(VisitDomainError) as ctx:
                uc.list_enrollments(kind, permissions=READ, order=order)
            self.assertEqual(ctx.exception.status_code, 422)

    def test_order_param_through_the_api(self):
        client_api, _ = _login_client("orden_api", READ)
        self._enroll("EXP-API-SIN")
        response = client_api.get("/api/v1/padrones/cronicos?order=prioridad")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["total"], 1)
