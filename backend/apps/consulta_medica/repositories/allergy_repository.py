from apps.catalogos.models import CatTipoAlergia
from apps.consulta_medica.models import Allergy, AllergyRevision

# Campos editables via update() -- se usa para saber que "previous_<campo>"
# snapshotear en AllergyRevision. No incluye no_exp/pk_num/source/is_active
# (identidad/trazabilidad del registro, no un dato clinico que se corrija).
_VERSIONED_FIELDS = (
    "allergy_type_id",
    "substance",
    "medication_id",
    "severity",
    "reaction",
)


class AllergyRepository:
    @staticmethod
    def list_for_patient(no_exp, pk_num):
        return Allergy.objects.select_related("allergy_type").filter(
            no_exp=no_exp, pk_num=pk_num, is_active=True,
        ).order_by("created_at")

    @staticmethod
    def get_active_by_id(allergy_id, no_exp, pk_num):
        return Allergy.objects.filter(
            pk=allergy_id, no_exp=no_exp, pk_num=pk_num, is_active=True,
        ).first()

    @staticmethod
    def list_active_medication_allergies(no_exp, pk_num):
        """Alergias activas de categoria MEDICATION -- usado por el cruce
        receta<->alergia (ver `prescription_item_usecase.add_prescription_item`).
        Una alergia RESUELTA sigue visible como historia pero ya no alerta."""
        return Allergy.objects.filter(
            no_exp=no_exp,
            pk_num=pk_num,
            is_active=True,
            status=Allergy.Status.ACTIVE,
            allergy_type_id=CatTipoAlergia.MEDICATION,
        )

    @staticmethod
    def create(*, no_exp, pk_num, allergy_type_id, substance, severity, source, medication_id=None, reaction=None, created_by_id=None):
        return Allergy.objects.create(
            no_exp=no_exp,
            pk_num=pk_num,
            allergy_type_id=allergy_type_id,
            substance=substance,
            medication_id=medication_id,
            severity=severity,
            reaction=reaction,
            service_origin_code=Allergy.SERVICE_BY_SOURCE[source],
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )

    @staticmethod
    def update(allergy, *, fields, updated_by_id=None):
        # A diferencia de ClinicalHistory (captura incremental, un campo
        # vacio no cuenta como "cambio"), una Allergy siempre se crea con
        # todos sus campos obligatorios completos -- cualquier edicion
        # posterior es una correccion real y se versiona siempre.
        AllergyRevision.objects.create(
            allergy=allergy,
            changed_by_id=updated_by_id,
            previous_allergy_type_id=allergy.allergy_type_id,
            previous_substance=allergy.substance,
            previous_medication_id=allergy.medication_id,
            previous_severity=allergy.severity,
            previous_reaction=allergy.reaction,
        )

        for field_name, value in fields.items():
            setattr(allergy, field_name, value)
        allergy.updated_by_id = updated_by_id
        allergy.save()
        if "allergy_type_id" in fields:
            # Evita servir el tipo anterior cacheado en la instancia.
            allergy.allergy_type = CatTipoAlergia.objects.get(pk=allergy.allergy_type_id)
        return allergy

    @staticmethod
    def deactivate(allergy, *, updated_by_id=None):
        from django.utils import timezone

        allergy.is_active = False
        allergy.status = Allergy.Status.ENTERED_IN_ERROR
        allergy.deleted_at = timezone.now()
        allergy.deleted_by_id = updated_by_id
        allergy.updated_by_id = updated_by_id
        allergy.save()
        return allergy

    @staticmethod
    def to_contract(allergy):
        return {
            "id": allergy.id_allergy,
            "noExp": allergy.no_exp,
            "pkNum": allergy.pk_num,
            "allergyTypeId": allergy.allergy_type_id,
            "allergyTypeName": allergy.allergy_type.name,
            "substance": allergy.substance,
            "medicationId": allergy.medication_id,
            "severity": allergy.severity,
            "reaction": allergy.reaction,
            "source": allergy.source,
            "status": allergy.status,
            "statusReason": allergy.status_reason,
            "isActive": allergy.is_active,
            "createdAt": allergy.created_at,
            "updatedAt": allergy.updated_at,
        }
