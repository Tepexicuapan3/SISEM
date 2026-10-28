"""
apps/consulta_medica/impresion/receta.py
============================================
Builder de la Receta para el modulo ``impresion`` (solo lectura).

Hojas en un solo PDF: ORIGINAL y COPIA siempre; CONTROLADO si algun
medicamento es controlado (solo esos renglones). La hoja ANTIBIOTICO queda
fuera hasta que farmacia la confirme (decision 2026-10-16).

Reglas de imprimibilidad (R4.2): consulta cerrada, nota no cancelada y sin
autorizacion pendiente o rechazada. No replica efectos del legado
(ope_autorizacion, det_impresionrecetas).
"""

import json
from zoneinfo import ZoneInfo

from django.db.models import TextField
from django.db.models.functions import Cast

from apps.catalogos.services.parametro_service import get_param
from apps.consulta_medica.impresion.common import (
    VISIT_CLOSED,
    center_of,
    doctor_info,
    fmt_date,
    get_consultation,
    get_visit_or_404,
    is_note_cancelled,
    not_printable,
    patient_header_or_409,
)
from apps.consulta_medica.models import (
    PrescriptionAuthorization,
    VisitPrescription,
    VisitPrescriptionItem,
)
from apps.impresion.errors import PrintError
from apps.impresion.registry import PrintContext
from apps.consulta_medica.services.paciente_entrada import llave_publica

PRINT_TZ = ZoneInfo("America/Mexico_City")

SHEET_ORIGINAL = "ORIGINAL"
SHEET_COPIA = "COPIA"
SHEET_CONTROLADO = "CONTROLADO"

_BLOCKING_AUTH = {
    PrescriptionAuthorization.Status.PENDIENTE: "La receta tiene una autorizacion pendiente.",
    PrescriptionAuthorization.Status.RECHAZADA: "La autorizacion de la receta fue rechazada.",
}


def _general_indications(prescription_id):
    """Indicaciones de texto libre (``items``). Se leen casteadas a texto:
    la columna es ``json`` (no jsonb) y leerla por el ORM falla en Postgres."""
    raw = (
        VisitPrescription.objects.filter(pk=prescription_id)
        .annotate(items_txt=Cast("items", TextField()))
        .values_list("items_txt", flat=True)
        .first()
    )
    try:
        items = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return [str(i).strip() for i in items if str(i).strip()] if isinstance(items, list) else []


def _ensure_authorized(prescription):
    latest = (
        PrescriptionAuthorization.objects.filter(prescription=prescription)
        .order_by("-created_at", "-pk")
        .values_list("status", flat=True)
        .first()
    )
    if latest in _BLOCKING_AUTH:
        raise not_printable(_BLOCKING_AUTH[latest])


def _item_row(item):
    med = item.medication
    return {
        "name": med.name,
        "generic_name": med.generic_name or "",
        "presentation": med.presentation or "",
        "dose": item.dose or "",
        "quantity": item.quantity,
        "indications": item.indications,
        "is_controlled": med.is_controlled,
    }


def build_sheets(rows):
    """Hojas a imprimir. Funcion pura para poder probar la seleccion."""
    sheets = [
        {"label": SHEET_ORIGINAL, "items": rows},
        {"label": SHEET_COPIA, "items": rows},
    ]
    controlled = [r for r in rows if r["is_controlled"]]
    if controlled:
        sheets.append({"label": SHEET_CONTROLADO, "items": controlled})
    return sheets


def build_receta_context(visit_id, actor, *, permissions=None, roles=None):
    visit = get_visit_or_404(visit_id)
    prescription = (
        VisitPrescription.objects.defer("items")
        .filter(id_visit=visit, is_active=True)
        .first()
    )
    if prescription is None:
        raise PrintError(
            code="PRESCRIPTION_NOT_FOUND", message="La visita no tiene receta.", status_code=404
        )

    consultation = get_consultation(visit)
    if is_note_cancelled(visit, consultation):
        raise not_printable("La nota esta cancelada; su receta no se puede imprimir.")
    if consultation is None or visit.status != VISIT_CLOSED:
        raise not_printable("La receta solo se imprime con la consulta cerrada.")
    _ensure_authorized(prescription)

    items = (
        VisitPrescriptionItem.objects.select_related("medication")
        .filter(prescription=prescription, status=VisitPrescriptionItem.Status.ACTIVO)
        .order_by("pk")
    )
    rows = [_item_row(i) for i in items]
    if not rows:
        raise not_printable("La receta no tiene medicamentos activos.")

    header = patient_header_or_409(visit)
    center = center_of(visit)
    folio = prescription.folio or ""
    issued = prescription.created_at.astimezone(PRINT_TZ) if prescription.created_at else None
    context = {
        "doc_title": "Receta médica",
        "folio": folio,
        "prescription_type": prescription.get_prescription_type_display(),
        "issued_date": fmt_date(issued),
        "patient": header,
        "expediente": llave_publica(visit)[0] or "",
        "doctor": doctor_info(consultation.doctor),
        "center_name": getattr(center, "name", "") or "",
        "consultorio": getattr(visit.consultorio, "name", "") if visit.consultorio else "",
        "general_indications": _general_indications(prescription.pk),
        # ope_param.ds_mreceta del legado, ahora parametro por centro.
        "legend": get_param("receta.leyenda", center_id=getattr(center, "pk", None), default=""),
        "sheets": build_sheets(rows),
    }
    return PrintContext(
        context=context,
        no_exp=llave_publica(visit)[0],
        pk_num=llave_publica(visit)[1],
        folio=folio,
        filename=f"receta_{folio or visit.folio}.pdf",
        is_cancelled=False,
        center_id=getattr(center, "pk", None),
        legacy_cd_clinica=getattr(center, "legacy_cd_clinica", None),
        source=prescription,
    )
