"""Mi jornada: consultas que el medico cerro hoy, con el estado de su receta.

La consulta cerrada ya no esta en la cola del medico; desde aqui la sigue
viendo e imprime la receta sin ir al expediente (NOM-024: disponibilidad).
"""

from datetime import date, datetime, timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.authentication.models import SyUsuario
from apps.catalogos.models import Medicamentos
from apps.consulta_medica.models import (
    PrescriptionAuthorization,
    VisitConsultation,
    VisitPrescription,
    VisitPrescriptionItem,
)
from apps.consulta_medica.repositories.prescription_authorization_repository import (
    PrescriptionAuthorizationRepository,
)
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave
from apps.consulta_medica.uses_case.attended_today_usecase import (
    MX_TZ,
    list_attended_today,
)
from apps.recepcion.models import Visit

TODAY = date(2026, 11, 13)


class AttendedTodayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doctor = SyUsuario.objects.create(usuario="dr_jornada", clave_hash="x")
        cls.other_doctor = SyUsuario.objects.create(usuario="dr_otro", clave_hash="x")
        cls.paracetamol = Medicamentos.objects.create(name="Paracetamol 500mg")
        cls.clonazepam = Medicamentos.objects.create(name="Clonazepam 2mg", is_controlled=True)

    def _visit(self, folio, *, doctor=None, status="cerrada", day=TODAY, active=True, name="PEREZ JUAN"):
        visit = Visit.objects.create(
            folio=folio, patient=_paciente_de_llave(f"EXP-{folio}", 0), arrival_type="walk_in",
            service_type="medicina_general", status=status, nombre_paciente=name,
        )
        consultation = VisitConsultation.objects.create(
            id_visit=visit, doctor=doctor or self.doctor, final_note="Nota", is_active=active,
        )
        at = datetime(day.year, day.month, day.day, 10, 0, tzinfo=MX_TZ)
        VisitConsultation.objects.filter(pk=consultation.pk).update(created_at=at, updated_at=at)
        return visit

    def _prescription(self, visit, meds):
        rx = VisitPrescription.objects.create(id_visit=visit, items=[], folio=f"RX-{visit.folio}")
        for med in meds:
            VisitPrescriptionItem.objects.create(
                prescription=rx, medication=med, dose="1 tab", indications="Cada 8 h", quantity=1,
            )
        return rx

    def _authorization(self, visit, status, reason=None):
        authorization = PrescriptionAuthorizationRepository.create(
            VisitPrescription.objects.get(id_visit=visit), visit, prescribed_by_id=self.doctor.id_usuario,
            medications_count=1, specialized_count=1, controlled_count=0,
        )
        PrescriptionAuthorization.objects.filter(pk=authorization.pk).update(status=status, rejection_reason=reason)

    def _items(self, today=TODAY):
        return list_attended_today(self.doctor.id_usuario, ["DOCTOR"], [], today=today)["items"]

    def test_lists_only_my_closed_consultations_of_today(self):
        self._visit("J-1")
        self._visit("J-2", doctor=self.other_doctor)
        self._visit("J-3", status="en_consulta")
        self._visit("J-4", day=TODAY - timedelta(days=1))
        self._visit("J-5", active=False)
        self.assertEqual([i["folio"] for i in self._items()], ["J-1"])

    def test_item_carries_patient_identity(self):
        self._visit("J-6", name="GOMEZ ANA")
        item = self._items()[0]
        self.assertEqual(item["nombrePaciente"], "GOMEZ ANA")
        self.assertEqual(item["noExp"], "EXP-J-6")
        self.assertIn("visitId", item)
        self.assertTrue(item["attendedAt"])

    def test_without_prescription(self):
        self._visit("J-7")
        self.assertIsNone(self._items()[0]["prescription"])

    def test_prescription_without_medications_is_not_printable(self):
        self._prescription(self._visit("J-8"), [])
        rx = self._items()[0]["prescription"]
        self.assertEqual(rx["medicationsCount"], 0)
        self.assertFalse(rx["printable"])

    def test_printable_prescription(self):
        self._prescription(self._visit("J-9"), [self.paracetamol, self.clonazepam])
        rx = self._items()[0]["prescription"]
        self.assertEqual(rx["folio"], "RX-J-9")
        self.assertEqual(rx["medicationsCount"], 2)
        self.assertTrue(rx["hasControlled"])
        self.assertIsNone(rx["authorization"])
        self.assertTrue(rx["printable"])

    def test_pending_or_rejected_authorization_blocks_printing(self):
        for folio, status in (("J-10", "pendiente"), ("J-11", "rechazada"), ("J-12", "autorizada")):
            visit = self._visit(folio)
            self._prescription(visit, [self.paracetamol])
            self._authorization(visit, status, "Sin justificacion" if status == "rechazada" else None)
        by_folio = {i["folio"]: i["prescription"] for i in self._items()}
        self.assertFalse(by_folio["J-10"]["printable"])
        self.assertFalse(by_folio["J-11"]["printable"])
        self.assertEqual(by_folio["J-11"]["authorization"]["rejectionReason"], "Sin justificacion")
        self.assertTrue(by_folio["J-12"]["printable"])

    def test_most_recent_first(self):
        first = self._visit("J-13")
        self._visit("J-14")
        VisitConsultation.objects.filter(id_visit=first).update(
            updated_at=datetime(2026, 11, 13, 12, 0, tzinfo=MX_TZ)
        )
        self.assertEqual([i["folio"] for i in self._items()], ["J-13", "J-14"])

    def test_requires_doctor_role(self):
        from apps.recepcion.services.errors import VisitDomainError

        with self.assertRaises(VisitDomainError):
            list_attended_today(self.doctor.id_usuario, ["RECEPCION"], [], today=TODAY)


class AttendedTodayViewTests(TestCase):
    def test_endpoint_returns_the_use_case_payload(self):
        user = SyUsuario.objects.create(usuario="dr_view", clave_hash="x")
        payload = {"items": [], "total": 0}
        with mock.patch("apps.consulta_medica.views._auth_or_error", return_value=(user, None)), \
                mock.patch("apps.consulta_medica.views._actor_context", return_value=(7, ["DOCTOR"], [])), \
                mock.patch("apps.consulta_medica.views.list_attended_today", return_value=payload) as use_case:
            response = APIClient().get(reverse("doctor-attended-today"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        use_case.assert_called_once_with(7, ["DOCTOR"], [])
