"""Repositorio APPEND-ONLY de la cancelacion de nota (sin update ni delete).

Change cancelacion-nota-cascada. El snapshot canonico solo se lee via
`.values("canonical_snapshot")` / get_snapshot_text para no depender de la
normalizacion de ningun campo JSON.
"""
from apps.consulta_medica.models import ConsultationCancellation, ConsultationCancellationItem


class ConsultationCancellationRepository:
    @staticmethod
    def get_for_consultation(consultation_id):
        return (
            ConsultationCancellation.objects.select_related("reason", "authorizer", "center")
            .filter(consultation_id=consultation_id)
            .first()
        )

    @staticmethod
    def get_by_visit(visit_id):
        return (
            ConsultationCancellation.objects.select_related("reason", "authorizer", "center")
            .filter(visit_id=visit_id)
            .first()
        )

    @staticmethod
    def get_snapshot_text(cancellation_id):
        return (
            ConsultationCancellation.objects.filter(pk=cancellation_id)
            .values_list("canonical_snapshot", flat=True)
            .first()
        )

    @staticmethod
    def create_header(
        *,
        consultation,
        visit,
        reason,
        reason_detail,
        authorizer,
        designation_id,
        applied_scope,
        center_id,
        outside_assignment,
        signature_method,
        canonical_snapshot,
        content_hash,
        signed_at,
        snapshot_version=1,
    ):
        return ConsultationCancellation.objects.create(
            consultation=consultation,
            visit=visit,
            reason=reason,
            reason_detail=reason_detail,
            authorizer=authorizer,
            designation_id=designation_id,
            applied_scope=applied_scope,
            center_id=center_id,
            outside_assignment=outside_assignment,
            signature_method=signature_method,
            snapshot_version=snapshot_version,
            canonical_snapshot=canonical_snapshot,
            content_hash=content_hash,
            signed_at=signed_at,
        )

    @staticmethod
    def add_items(cancellation, rows):
        """rows: iterable de (entity_type, entity_id, previous_status, new_status)."""
        return ConsultationCancellationItem.objects.bulk_create(
            [
                ConsultationCancellationItem(
                    cancellation=cancellation,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    previous_status=previous_status,
                    new_status=new_status,
                )
                for entity_type, entity_id, previous_status, new_status in rows
            ]
        )

    @staticmethod
    def list_items(cancellation_id):
        return list(
            ConsultationCancellationItem.objects.filter(cancellation_id=cancellation_id)
            .order_by("pk")
        )

    @staticmethod
    def to_contract(cancellation):
        return {
            "cancellationId": cancellation.id_cancellation,
            "visitId": cancellation.visit_id,
            "consultationId": cancellation.consultation_id,
            "motivoId": cancellation.reason_id,
            "motivoNombre": cancellation.reason.name,
            "motivoDetalle": cancellation.reason_detail,
            "autorizadorId": cancellation.authorizer_id,
            "alcanceAplicado": cancellation.applied_scope,
            "centroId": cancellation.center_id,
            "fueraAdscripcion": cancellation.outside_assignment,
            "metodoFirma": cancellation.signature_method,
            "hashContenido": cancellation.content_hash,
            "firmadoEn": cancellation.signed_at,
            "createdAt": cancellation.created_at,
        }
