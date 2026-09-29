from apps.consulta_medica.models import StomatologyHistory, StomatologyHistoryRevision

# Campos editables via upsert_stomatology_history (HC_ESTOMATOLOGIA) -- mismo
# set que STOMATOLOGY_HISTORY_FIELD_MAP. Se usa para saber que
# "previous_<campo>" snapshotear en StomatologyHistoryRevision.
_VERSIONED_FIELDS = (
    "oral_hygiene",
    "brushings_per_day",
    "uses_floss",
    "soft_tissues",
    "tmj",
)


class StomatologyHistoryRepository:
    @staticmethod
    def get_or_create_for_patient(no_exp, pk_num):
        """HC_ESTOMATOLOGIA cuelga de la HISTORIA_CLINICA unica del paciente
        (documento 5.3): si no existe, se abre junto con su PACIENTE."""
        from apps.consulta_medica.repositories.clinical_history_repository import (
            ClinicalHistoryRepository,
        )

        clinical_history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
        history, created = StomatologyHistory.objects.get_or_create(
            no_exp=no_exp,
            pk_num=pk_num,
            defaults={"clinical_history": clinical_history},
        )
        return history, created

    @staticmethod
    def update(history, *, fields, updated_by_id=None):
        # Mismo criterio que ClinicalHistoryRepository.update: captura
        # incremental, solo versiona si un campo YA tenia valor concreto y
        # se sobreescribe con otro.
        changed = any(
            field_name in _VERSIONED_FIELDS
            and getattr(history, field_name) not in (None, "")
            and getattr(history, field_name) != value
            for field_name, value in fields.items()
        )
        if changed:
            StomatologyHistoryRevision.objects.create(
                history=history,
                changed_by_id=updated_by_id,
                **{
                    f"previous_{field_name}": getattr(history, field_name)
                    for field_name in _VERSIONED_FIELDS
                },
            )

        for field_name, value in fields.items():
            setattr(history, field_name, value)
        history.updated_by_id = updated_by_id
        history.save()
        return history

    @staticmethod
    def to_contract(history):
        return {
            "id": history.id_stomatology_history,
            "noExp": history.no_exp,
            "pkNum": history.pk_num,
            "oralHygiene": history.oral_hygiene,
            "brushingsPerDay": history.brushings_per_day,
            "usesFloss": history.uses_floss,
            "softTissues": history.soft_tissues,
            "tmj": history.tmj,
            "isActive": history.is_active,
            "createdAt": history.created_at,
            "updatedAt": history.updated_at,
        }
