"""
Nucleo del paciente (documento "Historia Clinica Unificada", 5.1):
PACIENTE (ficha editable y versionada) 1:1 con HISTORIA_CLINICA (cabecera).
"""
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import EdoCivil, Ocupaciones
from apps.consulta_medica.models import ClinicalHistory, Patient, PatientRevision
from apps.consulta_medica.uses_case.clinical_history_usecase import (
    get_clinical_history,
    get_patient_profile,
    update_patient_profile,
)
from apps.recepcion.services.errors import VisitDomainError


def _noop_audit_hook(**kwargs):
    """Unit-level: el audit_hook se valida en los tests de API. `audit_hook`
    es keyword-only requerido (A0.3), asi que todo caller directo del
    usecase debe pasar algo."""
    return None


class PatientProfileUseCaseTests(TestCase):
    def setUp(self):
        self.no_exp = "EXP9001"
        self.pk_num = 0
        self.ocupacion_a = Ocupaciones.objects.create(name="Comerciante")
        self.ocupacion_b = Ocupaciones.objects.create(name="Empleado")
        self.edocivil = EdoCivil.objects.create(name="Soltero")

    def _update(self, data, actor_id=1):
        return update_patient_profile(
            self.no_exp, self.pk_num, ["DOCTOR"], data, actor_id=actor_id, audit_hook=_noop_audit_hook,
        )

    def _patient(self):
        return Patient.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)

    def test_first_update_creates_patient_and_history_one_to_one_without_revision(self):
        self._update({"occupationId": self.ocupacion_a.id, "phone": "5555555555"})

        patient = self._patient()
        history = ClinicalHistory.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)
        self.assertEqual(patient.occupation_id, self.ocupacion_a.id)
        self.assertEqual(history.patient_id, patient.id_patient)
        self.assertEqual(history.opened_on, timezone.localdate())
        self.assertEqual(PatientRevision.objects.filter(patient=patient).count(), 0)

    def test_second_update_with_different_values_creates_revision(self):
        self._update({"occupationId": self.ocupacion_a.id, "phone": "5555555555"})
        self._update({"occupationId": self.ocupacion_b.id, "phone": "6666666666"}, actor_id=2)

        patient = self._patient()
        self.assertEqual(patient.occupation_id, self.ocupacion_b.id)
        self.assertEqual(patient.phone, "6666666666")
        revision = PatientRevision.objects.get(patient=patient)
        self.assertEqual(revision.previous_occupation_id, self.ocupacion_a.id)
        self.assertEqual(revision.previous_phone, "5555555555")
        self.assertEqual(revision.changed_by_id, 2)

    def test_update_with_same_values_does_not_create_revision(self):
        self._update({"occupationId": self.ocupacion_a.id, "phone": "5555555555"})
        self._update({"occupationId": self.ocupacion_a.id, "phone": "5555555555"})

        self.assertEqual(PatientRevision.objects.count(), 0)

    def test_third_edit_accumulates_a_second_revision(self):
        self._update({"phone": "1111111111"})
        self._update({"phone": "2222222222"})
        self._update({"phone": "3333333333"})

        revisions = list(PatientRevision.objects.filter(patient=self._patient()).order_by("changed_at"))
        self.assertEqual([r.previous_phone for r in revisions], ["1111111111", "2222222222"])

    def test_clinical_history_is_read_only_header(self):
        header = get_clinical_history(self.no_exp, self.pk_num, ["DOCTOR"])
        profile = get_patient_profile(self.no_exp, self.pk_num, ["DOCTOR"])

        self.assertEqual(header["patientId"], profile["id"])
        self.assertEqual(header["openedOn"], timezone.localdate().isoformat())
        self.assertNotIn("phone", header)

    def test_reads_without_doctor_role_raise(self):
        with self.assertRaises(VisitDomainError):
            get_clinical_history(self.no_exp, self.pk_num, roles=["RECEPCION"])
        with self.assertRaises(VisitDomainError):
            get_patient_profile(self.no_exp, self.pk_num, roles=["RECEPCION"])
