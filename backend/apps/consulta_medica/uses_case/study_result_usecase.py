from django.db import transaction

from apps.catalogos.models import EstudiosMed
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.study_result_repository import StudyResultRepository
from apps.consulta_medica.services.visit_guards import (
    ensure_visit_not_cancelled,
    lock_visit_not_cancelled,
)
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError

from apps.consulta_medica.services.paciente_entrada import llave_publica
from .consultation_usecase import ensure_doctor_role


def _get_visit_or_error(visit_id):
    visit = VisitRepository.get_by_id(visit_id)
    if not visit:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    return visit


def create_study_result(
    visit_id,
    roles,
    *,
    study_type_id,
    result_date,
    notes,
    file,
    actor_id,
    permissions=None,
):
    ensure_doctor_role(roles, permissions)
    visit = _get_visit_or_error(visit_id)
    ensure_visit_not_cancelled(visit)

    consultation = ConsultationRepository.get_by_visit(visit)
    if consultation is None:
        raise VisitDomainError(
            "CONSULTATION_NOT_FOUND",
            "Primero debes guardar el diagnostico de esta consulta.",
            409,
        )

    study_type = EstudiosMed.objects.filter(pk=study_type_id, is_active=True).first()
    if study_type is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"studyTypeId": ["El tipo de estudio no existe o no esta activo."]},
        )

    with transaction.atomic():
        lock_visit_not_cancelled(visit.id_visit)
        result = StudyResultRepository.create(
            consultation=consultation,
            no_exp=llave_publica(visit)[0],
            pk_num=llave_publica(visit)[1],
            study_type=study_type,
            result_date=result_date,
            notes=notes,
            file=file,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
    return StudyResultRepository.to_contract(result)


def get_patient_study_results(no_exp, pk_num, roles, permissions=None, request=None):
    ensure_doctor_role(roles, permissions)

    results = StudyResultRepository.list_for_patient(no_exp, pk_num)
    items = [StudyResultRepository.to_contract(r, request=request) for r in results]
    return {"items": items, "total": len(items)}
