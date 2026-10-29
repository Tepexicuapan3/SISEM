"""Padrones clinicos de cronicos y discapacidad (P-04)."""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.administracion.models import AuditoriaEvento
from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Discapacidades, MotivoBajaPadron
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.consulta_medica.models import Patient
from apps.padrones.models import ChronicEnrollment, DisabilityEnrollment, RegistryStatus
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
CLASSIFY = "apps.consulta_medica.services.diagnosis_redaction_service.classify_cie"
TODAY = timezone.localdate()


def _vih_only(code):
    return ("VIH", "clinico:diagnosticos_vih:read") if (code or "").upper().startswith("B2") else None


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="medico_padron", clave_hash="x")
        cls.center = make_center()
        cls.diabetes = CatCies.objects.create(code="E11", description="DIABETES TIPO 2", version="CIE-10")
        cls.vih = CatCies.objects.create(code="B24", description="VIH", version="CIE-10")
        cls.disability = Discapacidades.objects.create(code="B1", name="FUNCIONES MENTALES")
        cls.reason = MotivoBajaPadron.objects.get(name="Defunción")

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _enroll(self, kind="cronicos", item_id="E11", **kw):
        data = dict(no_exp="EXP-PAD", pk_num=0, item_id=item_id, center_id=self.center.pk,
                    actor=self.actor, permissions=WRITE)
        data.update(kw)
        return uc.enroll(kind, **data)


class EnrollTests(_Base):
    def test_enroll_links_patient_through_existing_repository(self):
        enrollment = self._enroll()
        self.assertEqual(enrollment.status, RegistryStatus.ACTIVO)
        self.assertEqual(enrollment.enrolled_on, TODAY)
        self.assertEqual(enrollment.patient, Patient.objects.get(no_exp="EXP-PAD", pk_num=0))

    def test_same_disease_cannot_be_active_twice(self):
        self._enroll()
        with self.assertRaises(VisitDomainError) as ctx:
            self._enroll()
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("ALREADY_ENROLLED", 409))

    def test_other_disease_and_disability_are_independent(self):
        self._enroll()
        self._enroll(item_id="B24")
        self._enroll("discapacidad", item_id=str(self.disability.pk))
        self.assertEqual(ChronicEnrollment.objects.count(), 2)
        self.assertEqual(DisabilityEnrollment.objects.count(), 1)

    def test_validations(self):
        cases = [
            (dict(item_id="ZZZ"), "itemId"),
            (dict(no_exp="  "), "noExp"),
            (dict(enrolled_on=TODAY + timedelta(days=1)), "enrolledOn"),
            (dict(center_id=None), "centerId"),  # el actor no tiene centro de adscripcion
        ]
        for kwargs, field in cases:
            with self.subTest(field=field), self.assertRaises(VisitDomainError) as ctx:
                self._enroll(**kwargs)
            self.assertIn(field, ctx.exception.details)

    def test_permissions(self):
        with self.assertRaises(VisitDomainError) as ctx:
            self._enroll(permissions=["clinico:padrones:read"])
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(VisitDomainError):
            uc.list_enrollments("cronicos", permissions=["clinico:consultas:read"])

    def test_unknown_registry_404(self):
        with self.assertRaises(VisitDomainError) as ctx:
            self._enroll("otro")
        self.assertEqual(ctx.exception.status_code, 404)


class DischargeTests(_Base):
    def test_discharge_is_per_enrollment_and_keeps_history(self):
        diabetes = self._enroll()
        other = self._enroll(item_id="B24")
        done = uc.discharge("cronicos", diabetes.pk, reason_id=self.reason.pk, detail="  ",
                            actor=self.actor, permissions=WRITE)
        self.assertEqual(done.status, RegistryStatus.BAJA)
        self.assertEqual((done.discharge_reason, done.discharged_by, done.discharge_detail), (self.reason, self.actor, None))
        other.refresh_from_db()
        self.assertEqual(other.status, RegistryStatus.ACTIVO)  # el legado daba de baja al paciente completo
        self._enroll()  # tras la baja se puede volver a inscribir
        self.assertEqual(ChronicEnrollment.objects.filter(cie_id="E11").count(), 2)

    def test_discharge_rules(self):
        enrollment = self._enroll(enrolled_on=TODAY - timedelta(days=5))
        with self.assertRaises(VisitDomainError) as ctx:
            uc.discharge("cronicos", enrollment.pk, reason_id=self.reason.pk,
                         discharged_on=TODAY - timedelta(days=6), actor=self.actor, permissions=WRITE)
        self.assertIn("dischargedOn", ctx.exception.details)
        MotivoBajaPadron.objects.filter(pk=self.reason.pk).update(is_active=False)
        with self.assertRaises(VisitDomainError) as ctx:
            uc.discharge("cronicos", enrollment.pk, reason_id=self.reason.pk, actor=self.actor, permissions=WRITE)
        self.assertIn("reasonId", ctx.exception.details)

    def test_cannot_discharge_twice(self):
        enrollment = self._enroll()
        uc.discharge("cronicos", enrollment.pk, reason_id=self.reason.pk, actor=self.actor, permissions=WRITE)
        with self.assertRaises(VisitDomainError) as ctx:
            uc.discharge("cronicos", enrollment.pk, reason_id=self.reason.pk, actor=self.actor, permissions=WRITE)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("ENROLLMENT_ALREADY_DISCHARGED", 409))


class ListAndRedactionTests(_Base):
    def test_sensitive_diagnosis_redacted_without_permission(self):
        self._enroll(item_id="B24")
        with mock.patch(CLASSIFY, side_effect=_vih_only):
            hidden = uc.list_enrollments("cronicos", permissions=["clinico:padrones:read"])["items"][0]
            shown = uc.list_enrollments(
                "cronicos", permissions=["clinico:padrones:read", "clinico:diagnosticos_vih:read"],
            )["items"][0]
        self.assertTrue(hidden["item"]["restricted"])
        self.assertIsNone(hidden["item"]["code"])
        self.assertNotIn("VIH", hidden["item"]["description"])
        self.assertEqual(shown["item"]["code"], "B24")

    def test_filters_and_pagination(self):
        self._enroll()
        self._enroll(no_exp="EXP-OTRO")
        first = self._enroll(item_id="B24")
        uc.discharge("cronicos", first.pk, reason_id=self.reason.pk, actor=self.actor, permissions=WRITE)
        read = ["clinico:padrones:read"]
        self.assertEqual(uc.list_enrollments("cronicos", permissions=read, no_exp="EXP-PAD")["total"], 2)
        self.assertEqual(uc.list_enrollments("cronicos", permissions=read, status="activo")["total"], 2)
        page = uc.list_enrollments("cronicos", permissions=read, page_size=1, page=2)
        self.assertEqual((len(page["items"]), page["totalPages"]), (1, 3))


class PadronesApiTests(_Base):
    def setUp(self):
        super().setUp()
        self.client_api, self.user = _login_client("trabajo_social", WRITE)
        from apps.authentication.models import DetUsuario
        DetUsuario.objects.filter(id_usuario=self.user).update(id_centro_atencion=self.center)

    def test_requires_session(self):
        self.assertIn(APIClient().get("/api/v1/padrones/cronicos").status_code, (401, 403))

    def test_enroll_list_and_discharge_with_audit(self):
        created = self.client_api.post(
            "/api/v1/padrones/cronicos", {"idPaciente": _paciente_de_llave("EXP-API", 0).pk, "itemId": "E11"}, format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.data["center"]["id"], self.center.pk)  # centro de adscripcion
        self.assertTrue(AuditoriaEvento.objects.filter(accion="RegistryEnrollmentCreated").exists())

        listed = self.client_api.get("/api/v1/padrones/cronicos?noExp=EXP-API")
        self.assertEqual(listed.data["total"], 1)

        discharged = self.client_api.post(
            f"/api/v1/padrones/cronicos/{created.data['id']}/baja", {"reasonId": self.reason.pk}, format="json",
        )
        self.assertEqual(discharged.status_code, 200)
        self.assertEqual(discharged.data["discharge"]["reason"], "Defunción")
        self.assertTrue(AuditoriaEvento.objects.filter(accion="RegistryEnrollmentDischarged").exists())

    def test_validation_and_domain_errors(self):
        bad = self.client_api.post("/api/v1/padrones/cronicos", {"itemId": "E11"}, format="json")
        self.assertEqual(bad.status_code, 422)
        missing = self.client_api.post(
            "/api/v1/padrones/cronicos/999999/baja", {"reasonId": self.reason.pk}, format="json",
        )
        self.assertEqual((missing.status_code, missing.data["code"]), (404, "ENROLLMENT_NOT_FOUND"))

    def test_options_search_with_padron_permission_only(self):
        with mock.patch(CLASSIFY, side_effect=_vih_only):
            cie = self.client_api.get("/api/v1/padrones/cronicos/opciones?search=diab")
            hidden = self.client_api.get("/api/v1/padrones/cronicos/opciones?search=B2")
        self.assertEqual([i["code"] for i in cie.data["items"]], ["E11"])
        self.assertEqual(hidden.data["items"], [])  # sensibles sin permiso no se ofrecen
        disc = self.client_api.get("/api/v1/padrones/discapacidad/opciones?search=mental")
        self.assertEqual(disc.data["items"][0]["id"], self.disability.pk)
        self.assertEqual(self.client_api.get("/api/v1/padrones/cronicos/opciones?search=e").data["items"], [])

    def test_discharge_reasons_readable_with_padron_write(self):
        response = self.client_api.get("/api/v1/registry-discharge-reasons/")
        self.assertEqual(response.status_code, 200)
