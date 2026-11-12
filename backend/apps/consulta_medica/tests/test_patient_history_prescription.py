"""Historial de consultas: medicamentos de la receta (plan receta-flujo-impresion, F1).

El boton "Imprimir receta" del expediente depende de ``prescriptionMedications``:
los mismos renglones que imprime la receta (medicamentos activos), no las
indicaciones de texto libre (``prescriptionItems``).
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.authentication.models import SyUsuario
from apps.catalogos.models import Medicamentos
from apps.consulta_medica.models import VisitConsultation, VisitPrescription, VisitPrescriptionItem
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave
from apps.consulta_medica.uses_case.patient_history_usecase import get_patient_consultations_history
from apps.recepcion.models import Visit


class HistoryPrescriptionMedicationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doctor = SyUsuario.objects.create(usuario="dr_hist", clave_hash="x")
        cls.paracetamol = Medicamentos.objects.create(name="Paracetamol 500mg", generic_name="Paracetamol")
        cls.ibuprofeno = Medicamentos.objects.create(name="Ibuprofeno 400mg")

    def _visit(self, folio, no_exp="EXP-H1"):
        visit = Visit.objects.create(
            folio=folio, patient=_paciente_de_llave(no_exp, 0), arrival_type="walk_in",
            service_type="medicina_general", status="cerrada",
        )
        VisitConsultation.objects.create(id_visit=visit, doctor=self.doctor, final_note="Nota")
        return visit

    def _prescription(self, visit, meds, *, items=None):
        rx = VisitPrescription.objects.create(id_visit=visit, items=items or [], folio=f"RX-{visit.folio}")
        return [
            VisitPrescriptionItem.objects.create(
                prescription=rx, medication=med, dose="1 tab", indications="Cada 8 h", quantity=1,
            )
            for med in meds
        ]

    def _item(self, no_exp="EXP-H1"):
        return get_patient_consultations_history(no_exp, 0, ["DOCTOR"], permissions=[])["items"][0]

    def test_medications_without_free_text_indications(self):
        self._prescription(self._visit("H-1"), [self.paracetamol, self.ibuprofeno])
        item = self._item()
        self.assertEqual(item["prescriptionMedications"], ["Paracetamol 500mg", "Ibuprofeno 400mg"])
        self.assertEqual(item["prescriptionItems"], [])

    def test_cancelled_item_is_not_listed(self):
        first, _ = self._prescription(self._visit("H-2"), [self.paracetamol, self.ibuprofeno])
        first.status = VisitPrescriptionItem.Status.CANCELADO
        first.save(update_fields=["status"])
        self.assertEqual(self._item()["prescriptionMedications"], ["Ibuprofeno 400mg"])

    def test_only_free_text_indications_gives_no_medications(self):
        self._prescription(self._visit("H-3"), [], items=["Tomar liquidos"])
        item = self._item()
        self.assertEqual(item["prescriptionMedications"], [])
        self.assertEqual(item["prescriptionItems"], ["Tomar liquidos"])

    def test_history_item_carries_each_soap_section(self):
        visit = self._visit("H-6")
        VisitConsultation.objects.filter(id_visit=visit).update(
            subjective="Tos", objective="Faringe hiperemica", assessment="Faringitis", plan="Reposo",
        )
        item = self._item()
        self.assertEqual(
            (item["subjective"], item["objective"], item["assessment"], item["plan"]),
            ("Tos", "Faringe hiperemica", "Faringitis", "Reposo"),
        )

    def test_without_prescription(self):
        self._visit("H-4")
        self.assertEqual(self._item()["prescriptionMedications"], [])

    def test_medications_are_read_in_one_query_for_all_visits(self):
        for n in range(3):
            self._prescription(self._visit(f"H-5{n}", no_exp="EXP-H5"), [self.paracetamol])
        with CaptureQueriesContext(connection) as ctx:
            result = get_patient_consultations_history("EXP-H5", 0, ["DOCTOR"], permissions=[])
        self.assertEqual(len(result["items"]), 3)
        medication_queries = [
            q for q in ctx.captured_queries if "cns_visit_prescription_item" in q["sql"].lower()
        ]
        self.assertEqual(len(medication_queries), 1)


class HistoryPrescriptionAuthorizationTests(HistoryPrescriptionMedicationsTests):
    """El historial dice en que va la autorizacion de cada receta, para que el
    medico sepa si ya la puede imprimir."""

    def _authorization(self, visit, status, reason=None):
        from apps.consulta_medica.models import PrescriptionAuthorization
        from apps.consulta_medica.repositories.prescription_authorization_repository import (
            PrescriptionAuthorizationRepository,
        )

        authorization = PrescriptionAuthorizationRepository.create(
            VisitPrescription.objects.get(id_visit=visit), visit, prescribed_by_id=self.doctor.id_usuario,
            medications_count=1, specialized_count=1, controlled_count=0,
        )
        PrescriptionAuthorization.objects.filter(pk=authorization.pk).update(status=status, rejection_reason=reason)

    def test_folio_and_authorization_status(self):
        visit = self._visit("HA-1")
        self._prescription(visit, [self.paracetamol])
        self._authorization(visit, "rechazada", "Sin justificacion")

        item = self._item()
        self.assertEqual(item["prescriptionFolio"], "RX-HA-1")
        self.assertEqual(
            item["prescriptionAuthorization"], {"status": "rechazada", "rejectionReason": "Sin justificacion"},
        )

    def test_the_latest_authorization_wins(self):
        visit = self._visit("HA-2")
        self._prescription(visit, [self.paracetamol])
        self._authorization(visit, "autorizada")
        self._authorization(visit, "pendiente")
        self.assertEqual(self._item()["prescriptionAuthorization"]["status"], "pendiente")

    def test_without_authorization(self):
        self._prescription(self._visit("HA-3"), [self.paracetamol])
        self.assertIsNone(self._item()["prescriptionAuthorization"])

    def test_authorizations_are_read_in_one_query_for_all_visits(self):
        for n in range(3):
            visit = self._visit(f"HA-4{n}", no_exp="EXP-HA4")
            self._prescription(visit, [self.paracetamol])
            self._authorization(visit, "pendiente")
        with CaptureQueriesContext(connection) as ctx:
            get_patient_consultations_history("EXP-HA4", 0, ["DOCTOR"], permissions=[])
        queries = [q for q in ctx.captured_queries if "cns_prescription_authorization" in q["sql"].lower()]
        self.assertEqual(len(queries), 1)
