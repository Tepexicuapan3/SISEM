from apps.consulta_medica.models import VisitPrescription

# `SavePrescriptionsSerializer.items` (serializers.py) no acota la cantidad
# de indicaciones (ListField sin max_length) -- se acota aca, solo para el
# snapshot de auditoria, para no volcar una lista sin fin en
# `auditoria_eventos` (append-only). `itemsCount` siempre refleja el total
# real, sin truncar.
_AUDIT_ITEMS_LIMIT = 50


class PrescriptionRepository:
    @staticmethod
    def upsert_for_visit(
        visit,
        *,
        items,
        created_by_id=None,
        updated_by_id=None,
    ):
        existing = VisitPrescription.objects.filter(id_visit=visit).first()

        # Snapshot JSON-safe del estado previo para auditoria (NOM-024):
        # `items` es la unica excepcion en el diseno donde se guarda el
        # contenido completo (se reemplaza sin tabla de revisiones -- si
        # no se captura aca, la receta previa es irrecuperable).
        previous_snapshot = None
        if existing is not None:
            previous_items = list(existing.items or [])
            previous_snapshot = {
                "itemsCount": len(previous_items),
                "items": previous_items[:_AUDIT_ITEMS_LIMIT],
            }

        prescription, created = VisitPrescription.objects.update_or_create(
            id_visit=visit,
            defaults={
                "items": list(items),
                "is_active": True,
                "deleted_at": None,
                "deleted_by_id": None,
                "created_by_id": created_by_id,
                "updated_by_id": updated_by_id,
            },
        )
        return prescription, created, previous_snapshot

    @staticmethod
    def get_by_visit(visit):
        return VisitPrescription.objects.filter(id_visit=visit).first()

    @staticmethod
    def get_or_create_for_visit(visit, *, created_by_id=None, updated_by_id=None):
        """
        Usado por los items de receta estructurados (VisitPrescriptionItem):
        el doctor puede agregar medicamentos del catalogo sin haber
        capturado antes ninguna indicacion de texto libre.
        """
        prescription, _ = VisitPrescription.objects.get_or_create(
            id_visit=visit,
            defaults={
                "items": [],
                "created_by_id": created_by_id,
                "updated_by_id": updated_by_id,
            },
        )
        return prescription

    @staticmethod
    def to_contract(prescription):
        return {
            "id": prescription.id_prescription,
            "visitId": prescription.id_visit_id,
            "items": list(prescription.items or []),
            "isActive": prescription.is_active,
            "createdAt": prescription.created_at,
            "updatedAt": prescription.updated_at,
        }
