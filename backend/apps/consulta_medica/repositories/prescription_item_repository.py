from apps.consulta_medica.models import VisitPrescriptionItem


class PrescriptionItemRepository:
    @staticmethod
    def get_by_id(item_id):
        return VisitPrescriptionItem.objects.filter(pk=item_id, is_active=True).first()

    @staticmethod
    def get_active_by_prescription_and_medication(prescription, medication):
        return VisitPrescriptionItem.objects.filter(
            prescription=prescription,
            medication=medication,
            status=VisitPrescriptionItem.Status.ACTIVO,
            is_active=True,
        ).first()

    @staticmethod
    def create(
        *,
        prescription,
        medication,
        indications,
        quantity,
        dose=None,
        created_by_id=None,
        updated_by_id=None,
    ):
        return VisitPrescriptionItem.objects.create(
            prescription=prescription,
            medication=medication,
            indications=indications,
            quantity=quantity,
            dose=dose,
            created_by_id=created_by_id,
            updated_by_id=updated_by_id,
        )

    @staticmethod
    def cancel(item, *, updated_by_id=None):
        item.status = VisitPrescriptionItem.Status.CANCELADO
        item.updated_by_id = updated_by_id
        item.save(update_fields=["status", "updated_by_id", "updated_at"])
        return item

    @staticmethod
    def list_for_prescription(prescription):
        return (
            VisitPrescriptionItem.objects.filter(
                prescription=prescription,
                status=VisitPrescriptionItem.Status.ACTIVO,
                is_active=True,
            )
            .select_related("medication")
            .order_by("created_at")
        )

    @staticmethod
    def to_contract(item):
        return {
            "id": item.id_prescription_item,
            "visitId": item.prescription.id_visit_id,
            "prescriptionFolio": item.prescription.folio,
            "medicationId": item.medication_id,
            "medicationName": item.medication.name,
            "genericName": item.medication.generic_name,
            "presentation": item.medication.presentation,
            "dose": item.dose,
            "indications": item.indications,
            "quantity": item.quantity,
            "status": item.status,
            # Candado de receta (5.3): lo surtido ya no se quita.
            "dispensedQuantity": item.dispensed_quantity,
            "dispensationStatus": item.dispensation_status,
            "canCancel": item.status == VisitPrescriptionItem.Status.ACTIVO and item.dispensed_quantity == 0,
            "createdAt": item.created_at,
        }
