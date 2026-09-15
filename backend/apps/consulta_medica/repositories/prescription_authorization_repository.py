from django.utils import timezone

from apps.consulta_medica.models import PrescriptionAuthorization


class PrescriptionAuthorizationRepository:
    @staticmethod
    def get_pending_for_prescription(prescription):
        return PrescriptionAuthorization.objects.filter(
            prescription=prescription, status=PrescriptionAuthorization.Status.PENDIENTE,
        ).first()

    @staticmethod
    def create(
        prescription, visit, *,
        prescribed_by_id, medications_count, specialized_count, controlled_count,
    ):
        return PrescriptionAuthorization.objects.create(
            prescription=prescription,
            visit=visit,
            prescribed_by_id=prescribed_by_id,
            medications_count=medications_count,
            specialized_count=specialized_count,
            controlled_count=controlled_count,
        )

    @staticmethod
    def update_counts(authorization, *, medications_count, specialized_count, controlled_count):
        authorization.medications_count = medications_count
        authorization.specialized_count = specialized_count
        authorization.controlled_count = controlled_count
        authorization.save(update_fields=[
            "medications_count", "specialized_count", "controlled_count", "updated_at",
        ])
        return authorization

    @staticmethod
    def get_by_id(authorization_id):
        return (
            PrescriptionAuthorization.objects
            .select_related("visit")
            .filter(pk=authorization_id)
            .first()
        )

    @staticmethod
    def list_pending():
        return (
            PrescriptionAuthorization.objects
            .filter(status=PrescriptionAuthorization.Status.PENDIENTE)
            .select_related("visit")
            .order_by("created_at")
        )

    @staticmethod
    def list_history(*, status=None, date_from=None, date_to=None, limit=200):
        """
        Historial de auditoria (cualquier estatus, no solo pendientes) --
        trazabilidad NOM-024 de quien resolvio cada solicitud y cuando.
        Mas reciente primero; `limit` acotado por defecto para no devolver
        un historial sin fin en una sola respuesta.
        """
        queryset = PrescriptionAuthorization.objects.select_related("visit")

        if status:
            queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset.order_by("-created_at")[:limit]

    @staticmethod
    def authorize(authorization, *, authorized_by_id):
        authorization.status = PrescriptionAuthorization.Status.AUTORIZADA
        authorization.authorized_by_id = authorized_by_id
        authorization.authorized_at = timezone.now()
        authorization.save(update_fields=["status", "authorized_by_id", "authorized_at", "updated_at"])
        return authorization

    @staticmethod
    def reject(authorization, *, authorized_by_id, reason):
        authorization.status = PrescriptionAuthorization.Status.RECHAZADA
        authorization.authorized_by_id = authorized_by_id
        authorization.authorized_at = timezone.now()
        authorization.rejection_reason = reason
        authorization.save(update_fields=[
            "status", "authorized_by_id", "authorized_at", "rejection_reason", "updated_at",
        ])
        return authorization

    @staticmethod
    def to_contract(authorization):
        visit = authorization.visit
        return {
            "id": authorization.id_authorization,
            "prescriptionId": authorization.prescription_id,
            "visitId": visit.id_visit,
            "noExp": visit.no_exp,
            "pkNum": visit.pk_num,
            "prescribedById": authorization.prescribed_by_id,
            "medicationsCount": authorization.medications_count,
            "specializedCount": authorization.specialized_count,
            "controlledCount": authorization.controlled_count,
            "status": authorization.status,
            "authorizedById": authorization.authorized_by_id,
            "authorizedAt": authorization.authorized_at,
            "rejectionReason": authorization.rejection_reason,
            "createdAt": authorization.created_at,
        }
