"""
apps/consulta_medica/impresion/common.py
============================================
Piezas compartidas por los builders de receta y nota (solo lectura).
"""

from apps.consulta_medica.models import ConsultationCancellation, VisitConsultation
from apps.impresion.errors import PrintError
from apps.impresion.services.patient_header import get_patient_header
from apps.medicos import identity
from apps.recepcion.repositories.visit_repository import VisitRepository

VISIT_CLOSED = "cerrada"
VISIT_CANCELLED = "cancelada"


def not_printable(message):
    return PrintError(code="DOCUMENT_NOT_PRINTABLE", message=message, status_code=409)


def get_visit_or_404(visit_id):
    visit = VisitRepository.get_by_id(visit_id)
    if visit is None:
        raise PrintError(code="VISIT_NOT_FOUND", message="Visita no encontrada.", status_code=404)
    return visit


def get_consultation(visit):
    return VisitConsultation.objects.select_related("cie").filter(id_visit=visit).first()


def is_note_cancelled(visit, consultation):
    """Nota cancelada = visita cancelada o cabecera de cancelacion en cascada."""
    if visit.status == VISIT_CANCELLED:
        return True
    if consultation is None:
        return False
    return ConsultationCancellation.objects.filter(consultation=consultation).exists()


def patient_header_or_409(visit):
    header = get_patient_header(visit.no_exp, visit.pk_num, visit.nombre_paciente or "")
    if header["source"] is None:
        raise not_printable("No se pudo resolver el nombre del paciente.")
    return header


def doctor_info(user):
    """Nombre y cedula del medico que atendio (SyUsuario -> CatMedico)."""
    if user is None:
        return {"name": "", "cedula": ""}
    from apps.medicos.models import CatMedico

    medico = (
        CatMedico.objects.select_related(*identity.IDENTITY_SELECT)
        .prefetch_related(*identity.IDENTITY_PREFETCH)
        .filter(id_usuario_id=user.pk)
        .first()
    )
    if medico is not None:
        return {
            "name": identity.display_name(medico),
            "cedula": identity.cedula_profesional(medico) or "",
        }
    profile = getattr(user, "detalle", None)
    return {
        "name": getattr(profile, "nombre_completo", None) or getattr(user, "usuario", "") or "",
        "cedula": "",
    }


def center_of(visit):
    consultorio = visit.consultorio
    return getattr(consultorio, "id_center", None) if consultorio else None


def fmt_date(value):
    return value.strftime("%d/%m/%Y") if value else ""
