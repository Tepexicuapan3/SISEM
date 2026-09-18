from django.test import TestCase

from apps.catalogos.models import EdoCivil, Ocupaciones
from apps.consulta_medica.models import ClinicalHistory, ClinicalHistoryRevision
from apps.consulta_medica.uses_case.clinical_history_usecase import (
    get_clinical_history,
    upsert_clinical_history,
)
from apps.recepcion.services.errors import VisitDomainError


def _noop_audit_hook(**kwargs):
    """Unit-level: el audit_hook se valida en los tests de API. `audit_hook`
    es keyword-only requerido (A0.3), asi que todo caller directo del
    usecase debe pasar algo."""
    return None


class ClinicalHistoryUseCaseTests(TestCase):
    def setUp(self):
        self.no_exp = "EXP9001"
        self.pk_num = 0
        self.ocupacion_a = Ocupaciones.objects.create(name="Comerciante")
        self.ocupacion_b = Ocupaciones.objects.create(name="Empleado")
        self.edocivil = EdoCivil.objects.create(name="Soltero")

    def test_first_upsert_creates_history_without_revision(self):
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"occupationId": self.ocupacion_a.id, "phone": "5555555555"},
            actor_id=1,
            audit_hook=_noop_audit_hook,
        )

        history = ClinicalHistory.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)
        self.assertEqual(history.occupation_id, self.ocupacion_a.id)
        self.assertEqual(ClinicalHistoryRevision.objects.filter(history=history).count(), 0)

    def test_second_upsert_with_different_values_creates_revision(self):
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"occupationId": self.ocupacion_a.id, "phone": "5555555555"},
            actor_id=1,
            audit_hook=_noop_audit_hook,
        )

        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"occupationId": self.ocupacion_b.id, "phone": "6666666666"},
            actor_id=2,
            audit_hook=_noop_audit_hook,
        )

        history = ClinicalHistory.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)
        self.assertEqual(history.occupation_id, self.ocupacion_b.id)
        self.assertEqual(history.phone, "6666666666")

        revisions = ClinicalHistoryRevision.objects.filter(history=history)
        self.assertEqual(revisions.count(), 1)
        revision = revisions.first()
        self.assertEqual(revision.previous_occupation_id, self.ocupacion_a.id)
        self.assertEqual(revision.previous_phone, "5555555555")
        self.assertEqual(revision.changed_by_id, 2)

    def test_upsert_with_same_values_does_not_create_revision(self):
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"occupationId": self.ocupacion_a.id, "phone": "5555555555"},
            actor_id=1,
            audit_hook=_noop_audit_hook,
        )
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"occupationId": self.ocupacion_a.id, "phone": "5555555555"},
            actor_id=1,
            audit_hook=_noop_audit_hook,
        )

        history = ClinicalHistory.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)
        self.assertEqual(ClinicalHistoryRevision.objects.filter(history=history).count(), 0)

    def test_third_edit_accumulates_a_second_revision(self):
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"], {"phone": "1111111111"}, actor_id=1,
            audit_hook=_noop_audit_hook,
        )
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"], {"phone": "2222222222"}, actor_id=1,
            audit_hook=_noop_audit_hook,
        )
        upsert_clinical_history(
            self.no_exp, self.pk_num, ["DOCTOR"], {"phone": "3333333333"}, actor_id=1,
            audit_hook=_noop_audit_hook,
        )

        history = ClinicalHistory.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)
        revisions = list(
            ClinicalHistoryRevision.objects.filter(history=history).order_by("changed_at")
        )
        self.assertEqual(len(revisions), 2)
        self.assertEqual(revisions[0].previous_phone, "1111111111")
        self.assertEqual(revisions[1].previous_phone, "2222222222")

    def test_get_clinical_history_without_doctor_role_raises(self):
        with self.assertRaises(VisitDomainError):
            get_clinical_history(self.no_exp, self.pk_num, roles=["RECEPCION"])
