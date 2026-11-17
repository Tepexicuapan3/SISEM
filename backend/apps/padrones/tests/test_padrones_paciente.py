"""Padrones del paciente para la alerta del expediente
(docs/plans/padrones-alerta-expediente.md)."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Discapacidades, MotivoBajaPadron
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.services.errors import VisitDomainError

WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
EXPEDIENTE = ["clinico:expedientes:read"]
CLASSIFY = "apps.consulta_medica.services.diagnosis_redaction_service.classify_cie"


def _vih_only(code):
    return ("VIH", "clinico:diagnosticos_vih:read") if (code or "").upper().startswith("B2") else None


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="padrones_paciente", clave_hash="x")
        cls.center = make_center()
        for code, description in [("E11", "DIABETES TIPO 2"), ("I10", "HIPERTENSION"), ("B24", "VIH")]:
            CatCies.objects.get_or_create(code=code, defaults={"description": description, "version": "CIE-10"})
        cls.disability = Discapacidades.objects.create(code="B1", name="FUNCIONES MENTALES")
        cls.reason = MotivoBajaPadron.objects.get(name="Defunción")

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _enroll(self, kind="cronicos", item_id="E11", no_exp="EXP-PP"):
        return uc.enroll(kind, no_exp=no_exp, pk_num=0, item_id=item_id, center_id=self.center.pk,
                         actor=self.actor, permissions=WRITE)


class PatientRegistriesTests(_Base):
    def test_active_enrollments_of_both_registries_for_that_patient_only(self):
        diabetes = self._enroll()
        discharged = self._enroll(item_id="I10")
        uc.discharge("cronicos", discharged.pk, reason_id=self.reason.pk, actor=self.actor, permissions=WRITE)
        self._enroll("discapacidad", item_id=str(self.disability.pk))
        self._enroll(no_exp="EXP-OTRO")

        payload = uc.patient_registries(diabetes.patient_id, permissions=EXPEDIENTE)

        self.assertEqual([i["item"]["code"] for i in payload["cronicos"]], ["E11"])
        self.assertEqual(payload["cronicos"][0]["program"], {"code": "DIABETES", "name": "Diabetes mellitus"})
        self.assertIsNone(payload["cronicos"][0]["lastControl"])
        self.assertEqual([i["item"]["description"] for i in payload["discapacidad"]], ["FUNCIONES MENTALES"])

    def test_any_of_the_three_read_permissions(self):
        patient_id = self._enroll().patient_id
        for permissions in (["clinico:expedientes:read"], ["clinico:consultas:read"], ["clinico:padrones:read"]):
            with self.subTest(permissions=permissions):
                self.assertEqual(len(uc.patient_registries(patient_id, permissions=permissions)["cronicos"]), 1)
        with self.assertRaises(VisitDomainError) as ctx:
            uc.patient_registries(patient_id, permissions=["clinico:recepcion:read"])
        self.assertEqual(ctx.exception.status_code, 403)

    def test_sensitive_diagnosis_is_redacted(self):
        patient_id = self._enroll(item_id="B24").patient_id
        with mock.patch(CLASSIFY, side_effect=_vih_only):
            item = uc.patient_registries(patient_id, permissions=EXPEDIENTE)["cronicos"][0]
        self.assertTrue(item["item"]["restricted"])
        self.assertIsNone(item["item"]["code"])
        self.assertIsNone(item["program"])

    def test_unknown_patient_gives_empty_lists(self):
        self.assertEqual(uc.patient_registries(999999, permissions=EXPEDIENTE), {"cronicos": [], "discapacidad": []})


class PatientRegistriesApiTests(_Base):
    def test_endpoint(self):
        patient_id = self._enroll().patient_id
        client, _ = _login_client("lector_expediente", EXPEDIENTE)
        response = client.get(f"/api/v1/pacientes/{patient_id}/padrones")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data["cronicos"]), 1)

        denied, _ = _login_client("sin_permiso_padron", ["clinico:recepcion:read"])
        self.assertEqual(denied.get(f"/api/v1/pacientes/{patient_id}/padrones").status_code, 403)
