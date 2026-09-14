from apps.consulta_medica.models import ClinicalHistory, ClinicalHistoryRevision

# Campos editables via upsert_clinical_history -- mismo set que
# CLINICAL_HISTORY_FIELD_MAP en clinical_history_usecase.py. Se usa para
# saber que "previous_<campo>" snapshotear en ClinicalHistoryRevision.
_VERSIONED_FIELDS = (
    "occupation_id",
    "education_level_id",
    "marital_status_id",
    "religion_id",
    "residence_type_id",
    "phone",
    "family_history",
    "current_illness",
    "systems_review",
    "head_exam",
    "neck_exam",
    "chest_exam",
    "abdomen_exam",
    "genitals_exam",
    "limbs_exam",
    "diagnostic_management",
    "therapeutic_management",
    "allergies",
)


class ClinicalHistoryRepository:
    @staticmethod
    def get_or_create_for_patient(no_exp, pk_num):
        history, created = ClinicalHistory.objects.get_or_create(
            no_exp=no_exp,
            pk_num=pk_num,
        )
        return history, created

    @staticmethod
    def update(history, *, fields, updated_by_id=None):
        # ClinicalHistory se captura de forma incremental (ver docstring del
        # modelo): rellenar un campo vacio por primera vez no es una
        # alteracion de un dato clinico, es captura normal -- solo versiona
        # cuando YA habia un valor concreto y se sobreescribe con otro.
        changed = any(
            field_name in fields
            and getattr(history, field_name) not in (None, "")
            and getattr(history, field_name) != value
            for field_name, value in fields.items()
        )
        if changed:
            # Versionado real (NOM-024): se guarda un snapshot del valor
            # anterior ANTES de pisarlo -- nunca se sobrescribe sin dejar
            # rastro, mismo patron que VisitConsultation/VisitConsultationRevision.
            ClinicalHistoryRevision.objects.create(
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
            "id": history.id_clinical_history,
            "noExp": history.no_exp,
            "pkNum": history.pk_num,
            "occupationId": history.occupation_id,
            "educationLevelId": history.education_level_id,
            "maritalStatusId": history.marital_status_id,
            "religionId": history.religion_id,
            "residenceTypeId": history.residence_type_id,
            "phone": history.phone,
            "familyHistory": history.family_history,
            "currentIllness": history.current_illness,
            "systemsReview": history.systems_review,
            "headExam": history.head_exam,
            "neckExam": history.neck_exam,
            "chestExam": history.chest_exam,
            "abdomenExam": history.abdomen_exam,
            "genitalsExam": history.genitals_exam,
            "limbsExam": history.limbs_exam,
            "diagnosticManagement": history.diagnostic_management,
            "therapeuticManagement": history.therapeutic_management,
            "allergies": history.allergies,
            "isActive": history.is_active,
            "createdAt": history.created_at,
            "updatedAt": history.updated_at,
        }
