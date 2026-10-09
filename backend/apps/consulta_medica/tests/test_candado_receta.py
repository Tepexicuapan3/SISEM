"""
5.3 paso 1: candado de receta (antes his_notas.sw_receta). Lo que farmacia
ya surtio no se quita de la receta; el candado se calcula del propio renglon
(cantidad_dispensada), no de una bandera copiada.
"""
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.consulta_medica.models import VisitPrescriptionItem
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item


class PrescriptionLockTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        self.visit = self._visit_with_consultation()
        self.item = add_prescription_item(
            self.visit.id_visit, ["DOCTOR"], medication_id=self.med_basico.id, quantity=2,
            indications="Cada 8 horas", actor_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

    def _dispense(self, quantity, dispensation_status):
        # Lo que hace farmacia al surtir (prescription_dispensation_usecase).
        VisitPrescriptionItem.objects.filter(pk=self.item["id"]).update(
            dispensed_quantity=quantity, dispensation_status=dispensation_status,
        )

    def _cancel(self):
        return self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/prescription-items/{self.item['id']}/cancel",
            {}, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def _listed_item(self):
        response = self.client.get(f"/api/v1/visits/{self.visit.id_visit}/prescription-items")
        return next(item for item in response.data["items"] if item["id"] == self.item["id"])

    def test_sin_surtir_se_puede_quitar(self):
        self.assertTrue(self.item["canCancel"])

        response = self._cancel()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelado")
        self.assertFalse(response.data["canCancel"])

    def test_surtido_parcial_no_se_quita(self):
        self._dispense(1, VisitPrescriptionItem.DispensationStatus.PARCIAL)

        response = self._cancel()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "PRESCRIPTION_ITEM_DISPENSED")
        self.assertEqual(VisitPrescriptionItem.objects.get(pk=self.item["id"]).status, "activo")
        self.assertFalse(
            AuditoriaEvento.objects.filter(accion="PrescriptionItemCancelled", request_id=self.request_id).exists()
        )

    def test_surtido_completo_no_se_quita(self):
        self._dispense(2, VisitPrescriptionItem.DispensationStatus.DISPENSADO)

        self.assertEqual(self._cancel().status_code, status.HTTP_409_CONFLICT)

    def test_la_lista_dice_si_se_puede_quitar(self):
        self._dispense(1, VisitPrescriptionItem.DispensationStatus.PARCIAL)

        listed = self._listed_item()

        self.assertEqual(
            (listed["dispensedQuantity"], listed["dispensationStatus"], listed["canCancel"]),
            (1, "parcial", False),
        )
