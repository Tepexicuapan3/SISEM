from apps.consulta_medica.models import StomatologyHistory, StomatologyHistoryRevision

# Campos editables via upsert_stomatology_history -- mismo set que
# STOMATOLOGY_HISTORY_FIELD_MAP en stomatology_history_usecase.py, MENOS los
# 6 campos allergy_* (congelados, ver models.StomatologyHistory -- ya no se
# editan, reemplazados por Allergy). Se usa para saber que "previous_<campo>"
# snapshotear en StomatologyHistoryRevision.
_VERSIONED_FIELDS = (
    "family_diabetes",
    "family_cancer",
    "family_high_blood_pressure",
    "family_low_blood_pressure",
    "cause_of_death",
    "personal_diabetes",
    "personal_asthma",
    "personal_high_blood_pressure",
    "personal_low_blood_pressure",
    "personal_hepatitis",
    "personal_hiv",
    "personal_smoking",
    "personal_alcoholism",
    "personal_substance_abuse",
    "habits",
    "diet",
    "surgical_history",
    "traumatic_history",
    "current_illness_history",
)


class StomatologyHistoryRepository:
    @staticmethod
    def get_or_create_for_patient(no_exp, pk_num):
        history, created = StomatologyHistory.objects.get_or_create(
            no_exp=no_exp,
            pk_num=pk_num,
        )
        return history, created

    @staticmethod
    def update(history, *, fields, updated_by_id=None):
        # Mismo criterio que ClinicalHistoryRepository.update: captura
        # incremental, solo versiona si un campo YA tenia valor concreto y
        # se sobreescribe con otro (booleanos cuentan "False" como valor
        # concreto tambien -- default es False, no None).
        changed = any(
            field_name in fields
            and field_name in _VERSIONED_FIELDS
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
            "familyDiabetes": history.family_diabetes,
            "familyCancer": history.family_cancer,
            "familyHighBloodPressure": history.family_high_blood_pressure,
            "familyLowBloodPressure": history.family_low_blood_pressure,
            "causeOfDeath": history.cause_of_death,
            "personalDiabetes": history.personal_diabetes,
            "personalAsthma": history.personal_asthma,
            "personalHighBloodPressure": history.personal_high_blood_pressure,
            "personalLowBloodPressure": history.personal_low_blood_pressure,
            "personalHepatitis": history.personal_hepatitis,
            "personalHiv": history.personal_hiv,
            "personalSmoking": history.personal_smoking,
            "personalAlcoholism": history.personal_alcoholism,
            "personalSubstanceAbuse": history.personal_substance_abuse,
            "habits": history.habits,
            "diet": history.diet,
            "surgicalHistory": history.surgical_history,
            "traumaticHistory": history.traumatic_history,
            "currentIllnessHistory": history.current_illness_history,
            "isActive": history.is_active,
            "createdAt": history.created_at,
            "updatedAt": history.updated_at,
        }
