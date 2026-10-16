"""
apps/recepcion/impresion/ficha.py
=====================================
Builder de la Ficha de Consulta para el modulo ``impresion`` (solo lectura)
y renderer alterno ``docx`` (FICHA_ENGINE=docx, solo hosts Windows con Word).
"""

from apps.impresion.errors import PrintError
from apps.impresion.registry import PrintContext
from apps.impresion.services.barcode import code128_data_uri
from apps.impresion.services.patient_header import get_patient_header
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services import ficha_service


def _user_display_name(user):
    profile = getattr(user, "detalle", None)
    return getattr(profile, "nombre_completo", None) or getattr(user, "usuario", "") or ""


def _center(visit):
    consultorio = visit.consultorio
    return getattr(consultorio, "id_center", None) if consultorio else None


def build_ficha_context(visit_id, actor):
    visit = VisitRepository.get_by_id(visit_id)
    if visit is None:
        raise PrintError(
            code="VISIT_NOT_FOUND", message="Visita no encontrada.", status_code=404
        )

    header = get_patient_header(visit.no_exp, visit.pk_num, visit.nombre_paciente or "")
    if header["source"] is None:
        raise PrintError(
            code="DOCUMENT_NOT_PRINTABLE",
            message="No se pudo resolver el nombre del paciente para la ficha.",
            status_code=409,
        )

    nombre = {
        "a_paterno": header["paternal_surname"],
        "a_materno": header["maternal_surname"],
        "nombre_paciente": header["first_name"],
        "edad": header["age"],
        "fecha_nac": header["birth_date"],
    }
    context = ficha_service.build_context(
        visit, usuario_nombre=_user_display_name(actor), nombre=nombre
    )
    context["paciente_nombre_completo"] = header["full_name"]
    context["doc_title"] = "Ficha de consulta"
    try:
        context["barcode_uri"] = code128_data_uri(visit.folio) if visit.folio else ""
    except Exception:
        context["barcode_uri"] = ""

    center = _center(visit)
    return PrintContext(
        context=context,
        no_exp=visit.no_exp,
        pk_num=visit.pk_num,
        folio=visit.folio or "",
        filename=f"ficha_{visit.folio}.pdf",
        center_id=getattr(center, "pk", None),
        legacy_cd_clinica=getattr(center, "legacy_cd_clinica", None),
        source=visit,
    )


def render_ficha_docx(print_context, actor):
    """Camino legado (docxtpl + Word COM). NO es un rollback para Linux."""
    return ficha_service.generate_ficha_pdf(
        print_context.source, usuario_nombre=_user_display_name(actor)
    )
