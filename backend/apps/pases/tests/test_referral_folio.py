"""Folios con consecutivo (change folios-documentos). Antes el folio era
"<PFX>-<fecha hora al segundo>-<expediente>": dos documentos del mismo
paciente en el mismo segundo chocaban contra el unique (500)."""
import re
from datetime import date

from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase
from apps.consulta_medica.uses_case.medical_leave_usecase import create_medical_leave
from apps.pases.models import Referral
from apps.pases.uses_case.referral_usecase import create_referral
from apps.consulta_medica.services.paciente_entrada import llave_publica

FOLIO_RE = r"^{}-\d{{4}}-\d{{6}}$"


class DocumentFolioTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        self.visit = self._visit_with_consultation()
        self.doctor_id = self.doctor_user.id_usuario

    def _referral(self, referral_type):
        create_referral(
            self.visit.id_visit, ["DOCTOR"], referral_type=referral_type, actor_id=self.doctor_id,
        )
        return Referral.objects.get(referral_type=referral_type).folio

    def test_two_referrals_same_patient_same_second_get_distinct_folios(self):
        first = self._referral(Referral.ReferralType.ESPECIALIDAD)
        second = self._referral(Referral.ReferralType.HOSPITALIZACION)
        self.assertNotEqual(first, second)
        for folio in (first, second):
            self.assertRegex(folio, FOLIO_RE.format("REF"))
            self.assertNotIn(llave_publica(self.visit)[0], folio)
        self.assertEqual(int(second[-6:]), int(first[-6:]) + 1)

    def test_medical_leave_folio_has_no_patient_data(self):
        result = create_medical_leave(
            self.visit.id_visit, ["DOCTOR"], leave_type_id=self.leave_type.pk, days=2,
            start_date=date.today(), is_subsequent=False, actor_id=self.doctor_id,
        )
        self.assertTrue(re.match(FOLIO_RE.format("LIC"), result["folio"]), result["folio"])
        self.assertNotIn(llave_publica(self.visit)[0], result["folio"])
