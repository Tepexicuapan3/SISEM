from datetime import date

from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.recepcion.services.errors import VisitDomainError

# Reporte, no escritura: permiso propio en vez de reusar
# clinico:consultas:read (ese habilita tambien captura de consulta -- ver
# nota en navigation_permissions_seed.py sobre no repetir ese hueco).
DAILY_REPORT_PERMISSION_REQUIREMENT = {"allOf": ["clinico:reportes:read"]}


def ensure_report_permission(roles, permissions=None):
    permission_state = evaluate_permission_requirement(
        DAILY_REPORT_PERMISSION_REQUIREMENT, permissions or []
    )
    if permission_state["granted"]:
        return

    raise VisitDomainError(
        "ROLE_NOT_ALLOWED",
        "No tenes permiso para ejecutar esta accion.",
        403,
    )


def _doctor_name(doctor):
    if doctor is None:
        return None
    detalle = getattr(doctor, "detalle", None)
    return detalle.nombre_completo if detalle else None


def _consultorio_name(consultorio):
    return consultorio.name if consultorio else None


def _consultation_to_report_row(consultation):
    visit = consultation.id_visit
    return {
        "visitId": visit.id_visit,
        "folio": visit.folio,
        "date": visit.fecha_consulta,
        "time": visit.hora_consulta,
        "noExp": visit.no_exp,
        "pkNum": visit.pk_num,
        "patientName": visit.nombre_paciente,
        "serviceType": visit.service_type,
        "consultorio": _consultorio_name(visit.consultorio),
        "doctorId": consultation.doctor_id,
        "doctorName": _doctor_name(consultation.doctor),
        "primaryDiagnosis": consultation.primary_diagnosis,
        "cieCode": consultation.cie_id,
        "cieDescription": consultation.cie.description if consultation.cie else None,
    }


def get_daily_consultation_report(
    fecha_inicio: date,
    fecha_fin: date,
    roles,
    permissions=None,
    *,
    doctor_id=None,
    consultorio_id=None,
):
    ensure_report_permission(roles, permissions)

    if fecha_inicio > fecha_fin:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "fechaInicio no puede ser posterior a fechaFin.",
            422,
        )

    consultations = ConsultationRepository.list_daily_report(
        fecha_inicio, fecha_fin, doctor_id=doctor_id, consultorio_id=consultorio_id
    )
    items = [_consultation_to_report_row(c) for c in consultations]

    return {
        "items": items,
        "total": len(items),
        "fechaInicio": fecha_inicio,
        "fechaFin": fecha_fin,
    }
