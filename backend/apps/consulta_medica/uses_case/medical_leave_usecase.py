from datetime import timedelta

from django.db import transaction

from apps.folios.models import FolioType
from apps.folios.services.folio_service import next_folio
from apps.catalogos.models import Licencias
from apps.catalogos.services.parametro_service import get_param
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.medical_leave_repository import MedicalLeaveRepository
from apps.consulta_medica.services.visit_guards import (
    ensure_visit_not_cancelled,
    lock_visit_not_cancelled,
)
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError

from apps.consulta_medica.services.paciente_entrada import llave_publica
from .consultation_usecase import ensure_doctor_or_incapacidad_read_role, ensure_doctor_role

# Topes por centro en cat_parametro (incapacidad.max_dias[_maternidad]); estas
# constantes solo se usan si la definicion no existe (migracion sin correr).
DEFAULT_MAX_DAYS = 60
MATERNITY_MAX_DAYS = 90


def _max_days(leave_type, visit):
    consultorio = visit.consultorio
    center_id = getattr(consultorio, "id_center_id", None) if consultorio else None
    if _is_maternity(leave_type):
        return get_param("incapacidad.max_dias_maternidad", center_id=center_id, default=MATERNITY_MAX_DAYS)
    return get_param("incapacidad.max_dias", center_id=center_id, default=DEFAULT_MAX_DAYS)


def _get_visit_or_error(visit_id):
    visit = VisitRepository.get_by_id(visit_id)
    if not visit:
        raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)
    return visit


def _is_maternity(leave_type):
    # Coincidencia por nombre, no por ID fijo -- el catalogo es editable
    # desde el admin y su PK no esta garantizada entre ambientes.
    return "matern" in leave_type.name.lower()


def create_medical_leave(
    visit_id,
    roles,
    *,
    leave_type_id,
    days,
    start_date,
    is_subsequent,
    actor_id,
    permissions=None,
):
    ensure_doctor_role(roles, permissions)
    visit = _get_visit_or_error(visit_id)
    ensure_visit_not_cancelled(visit)

    if llave_publica(visit)[1] != 0:
        raise VisitDomainError(
            "LEAVE_TITULAR_ONLY",
            "Solo el titular puede recibir una incapacidad, no un familiar.",
            409,
        )

    consultation = ConsultationRepository.get_by_visit(visit)
    if consultation is None:
        raise VisitDomainError(
            "CONSULTATION_NOT_FOUND",
            "Primero debes guardar el diagnostico de esta consulta.",
            409,
        )

    if MedicalLeaveRepository.get_active_for_consultation(consultation):
        raise VisitDomainError(
            "LEAVE_ALREADY_EXISTS",
            "Ya existe una incapacidad activa para esta consulta.",
            409,
        )

    leave_type = Licencias.objects.filter(pk=leave_type_id, is_active=True).first()
    if leave_type is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"leaveTypeId": ["El tipo de licencia no existe o no esta activo."]},
        )

    max_days = _max_days(leave_type, visit)
    if days > max_days:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"days": [f"Maximo {max_days} dias para este tipo de licencia."]},
        )

    overlap = MedicalLeaveRepository.get_active_overlap_for_patient(
        llave_publica(visit)[0], llave_publica(visit)[1], start_date
    )
    if overlap:
        raise VisitDomainError(
            "LEAVE_OVERLAP",
            f"El paciente ya cuenta con una incapacidad vigente hasta {overlap.end_date}.",
            409,
        )

    end_date = start_date + timedelta(days=days - 1)
    with transaction.atomic():
        lock_visit_not_cancelled(visit.id_visit)
        folio = next_folio(FolioType.LICENCIA)
        leave = MedicalLeaveRepository.create(
            consultation=consultation,
            no_exp=llave_publica(visit)[0],
            pk_num=llave_publica(visit)[1],
            leave_type=leave_type,
            is_subsequent=is_subsequent,
            days=days,
            start_date=start_date,
            end_date=end_date,
            folio=folio,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
    return MedicalLeaveRepository.to_contract(leave)


def get_patient_medical_leaves(no_exp, pk_num, roles, permissions=None):
    # GET (consulta) acepta el permiso de solo lectura `recepcion:incapacidad:read`
    # ademas de DOCTOR/clinico:consultas:read -- ver docstring del guard.
    # create_medical_leave (POST, arriba) sigue exclusivo de ensure_doctor_role.
    ensure_doctor_or_incapacidad_read_role(roles, permissions)

    leaves = MedicalLeaveRepository.list_for_patient(no_exp, pk_num)
    items = [MedicalLeaveRepository.to_contract(leave) for leave in leaves]
    return {"items": items, "total": len(items)}
