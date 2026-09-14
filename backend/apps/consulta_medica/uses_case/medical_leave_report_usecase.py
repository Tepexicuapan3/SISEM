from apps.consulta_medica.repositories.medical_leave_repository import MedicalLeaveRepository
from apps.consulta_medica.uses_case.daily_report_usecase import ensure_report_permission
from apps.recepcion.services.errors import VisitDomainError


def get_medical_leave_report(
    fecha_inicio,
    fecha_fin,
    roles,
    permissions=None,
    *,
    leave_type_id=None,
    no_exp=None,
):
    """
    Reporte de incapacidades/licencias con fecha de inicio en el rango dado.
    Reusa el mismo permiso que el resto de "Reportes y Analitica Operativa"
    (clinico:reportes:read) -- ver daily_report_usecase.py.
    """
    ensure_report_permission(roles, permissions)

    if fecha_inicio > fecha_fin:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "fechaInicio no puede ser posterior a fechaFin.",
            422,
        )

    leaves = MedicalLeaveRepository.list_report(
        fecha_inicio, fecha_fin, leave_type_id=leave_type_id, no_exp=no_exp,
    )
    items = [MedicalLeaveRepository.to_report_row(leave) for leave in leaves]

    return {
        "items": items,
        "total": len(items),
        "fechaInicio": fecha_inicio,
        "fechaFin": fecha_fin,
    }
