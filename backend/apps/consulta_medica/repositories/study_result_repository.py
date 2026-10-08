from apps.consulta_medica.models import StudyResult
from apps.consulta_medica.services.patient_link_service import for_patient


class StudyResultRepository:
    @staticmethod
    def create(
        *,
        consultation,
        no_exp,
        pk_num,
        study_type,
        result_date,
        notes,
        file,
        created_by_id=None,
        updated_by_id=None,
    ):
        return StudyResult.objects.create(
            consultation=consultation,
            no_exp=no_exp,
            pk_num=pk_num,
            study_type=study_type,
            result_date=result_date,
            notes=notes,
            file=file,
            created_by_id=created_by_id,
            updated_by_id=updated_by_id,
        )

    @staticmethod
    def list_for_patient(no_exp, pk_num):
        return (
            for_patient(StudyResult.objects.filter(is_active=True), no_exp, pk_num)
            .select_related("study_type")
            .order_by("-result_date")
        )

    @staticmethod
    def to_contract(result, request=None):
        file_url = None
        if result.file:
            file_url = (
                request.build_absolute_uri(result.file.url)
                if request is not None
                else result.file.url
            )

        return {
            "id": result.id_study_result,
            "visitId": result.consultation.id_visit_id,
            "studyTypeId": result.study_type_id,
            "studyTypeName": result.study_type.name,
            "resultDate": result.result_date,
            "notes": result.notes,
            "fileUrl": file_url,
            "isActive": result.is_active,
            "createdAt": result.created_at,
        }
