"""
apps/consulta_medica/impresion/receta.py
============================================
Builder de la Receta para el modulo ``impresion`` (solo lectura).

Hojas en un solo PDF (separacion por destino del papel):
- ORIGINAL (paciente): solo lo no controlado; remite al folio de la hoja del
  controlado. Si todo es controlado y no hay indicaciones generales, no sale.
- COPIA (archivo de la clinica): todo, marcada "no valida para surtir".
- CONTROLADO (la retiene la farmacia): solo los controlados, folio con "-C".
Cada hoja dice que plantilla
de ``receta/hojas/`` la dibuja (formato STC, docs/plans/receta-diseno-stc.md). La hoja ANTIBIOTICO queda
fuera hasta que farmacia la confirme (decision 2026-10-16).

Reglas de imprimibilidad (R4.2): consulta cerrada, nota no cancelada y sin
autorizacion pendiente o rechazada. No replica efectos del legado
(ope_autorizacion, det_impresionrecetas).
"""

from zoneinfo import ZoneInfo

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
from apps.impresion.services.barcode import code128_data_uri
from apps.consulta_medica.services.paciente_entrada import llave_publica

PRINT_TZ = ZoneInfo("America/Mexico_City")

SHEET_ORIGINAL = "ORIGINAL"
SHEET_COPIA = "COPIA"
SHEET_CONTROLADO = "CONTROLADO"

CONTROLLED_FOLIO_SUFFIX = "-C"
COPY_NOTICE = "NO VÁLIDA PARA SURTIR"

_SHEETS_DIR = "consulta_medica/impresion/receta/hojas"
SHEET_TEMPLATE_NORMAL = f"{_SHEETS_DIR}/normal.html"
SHEET_TEMPLATE_CONTROLADO = f"{_SHEETS_DIR}/controlado.html"

# Diseno de ORIGINAL/COPIA por tipo de receta. Transcripcion comparte el
# normal hasta que tenga hoja propia.
_TEMPLATE_BY_TYPE = {
    VisitPrescription.PrescriptionType.NORMAL: SHEET_TEMPLATE_NORMAL,
    VisitPrescription.PrescriptionType.TRANSCRIPTION: SHEET_TEMPLATE_NORMAL,
}

# Renglones de medicamentos que caben en la zona de alto fijo de una hoja A5
# (receta-a5-cumplimiento, A2). Si hay mas, siguen en hojas de continuacion.
ROWS_PER_SHEET = 5

# Microtexto de seguridad entre renglones del formulario (solo decorativo).
_MICROTEXT = "SISTEMADETRANSPORTECOLECTIVOMETRO" * 30

_BLOCKING_AUTH = {
    PrescriptionAuthorization.Status.PENDIENTE: "La receta tiene una autorizacion pendiente.",
    PrescriptionAuthorization.Status.RECHAZADA: "La autorizacion de la receta fue rechazada.",
}


def _general_indications(items):
    """Indicaciones de texto libre (``VisitPrescription.items``) sin vacios."""
    if not isinstance(items, list):
        return []
    return [str(i).strip() for i in items if str(i).strip()]


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
    row = {
        "code": med.code or "",
        "name": med.name,
        "generic_name": med.generic_name or "",
        "presentation": med.presentation or "",
        "dose": item.dose or "",
        "route_label": item.get_route_display() if item.route else "",
        "frequency": item.frequency or "",
        "duration": item.duration or "",
        "quantity": item.quantity,
        "indications": item.indications,
        "is_controlled": med.is_controlled,
    }
    row["label"] = _drug_label(row)
    row["administration"] = _administration_text(row)
    return row


def _administration_text(row):
    """Dosis, via, frecuencia, duracion (RIS art. 30) e indicaciones en un
    renglon. Los renglones previos a D8 no tienen via/frecuencia/duracion y
    se imprimen como antes."""
    parts = (row["dose"], row["route_label"], row["frequency"], row["duration"], row["indications"])
    return " · ".join(p for p in parts if p)


def _drug_label(row):
    """Denominacion generica primero (RIS art. 31); el nombre del catalogo,
    que trae la concentracion, y la presentacion van debajo."""
    name, generic = row["name"] or "", row["generic_name"] or ""
    if not generic or generic.casefold() == name.casefold():
        primary, rest = generic or name, ()
    else:
        primary, rest = generic, (name,)
    secondary = ". ".join(p for p in (*rest, row["presentation"]) if p)
    return {"primary": primary, "secondary": secondary}


def _paged(label, template, rows, stamp, *, notice=None, folio_suffix="", controlled_ref_suffix=""):
    """Una hoja por cada ROWS_PER_SHEET renglones: lo que no cabe sigue en
    hojas de continuacion ("Hoja i de n") con la numeracion corrida."""
    chunks = [rows[i:i + ROWS_PER_SHEET] for i in range(0, len(rows), ROWS_PER_SHEET)] or [[]]
    return [
        {
            "label": label, "template": template, "items": chunk, "stamp": stamp,
            "page": page, "pages": len(chunks), "last": page == len(chunks),
            "first_number": (page - 1) * ROWS_PER_SHEET + 1,
            "notice": notice, "folio_suffix": folio_suffix,
            "controlled_ref_suffix": controlled_ref_suffix,
        }
        for page, chunk in enumerate(chunks, start=1)
    ]


def build_sheets(rows, prescription_type, *, has_general_indications=False):
    """Hojas a imprimir y el diseno de cada una. Funcion pura para poder
    probar la seleccion.

    El controlado no va en el ORIGINAL: la farmacia retiene su hoja, y un
    segundo papel con el mismo medicamento se podria surtir dos veces."""
    template = _TEMPLATE_BY_TYPE.get(prescription_type, SHEET_TEMPLATE_NORMAL)
    controlled = [r for r in rows if r["is_controlled"]]
    general = [r for r in rows if not r["is_controlled"]]
    ref = CONTROLLED_FOLIO_SUFFIX if controlled else ""

    sheets = []
    if general or has_general_indications:
        sheets += _paged(SHEET_ORIGINAL, template, general, None, controlled_ref_suffix=ref)
    sheets += _paged(SHEET_COPIA, template, rows, SHEET_COPIA, notice=COPY_NOTICE)
    if controlled:
        sheets += _paged(
            SHEET_CONTROLADO, SHEET_TEMPLATE_CONTROLADO, controlled, None,
            folio_suffix=CONTROLLED_FOLIO_SUFFIX,
        )
    return sheets


def _date_boxes(text):
    """'dd/mm/aaaa' -> casillas Dia/Mes/Año del formulario."""
    parts = (text or "").split("/")
    if len(parts) != 3:
        return {"d": "", "m": "", "y": ""}
    return dict(zip(("d", "m", "y"), parts))


def _center_address(center):
    if center is None:
        return {"line1": "", "line2": ""}
    line1 = (center.address, center.neighborhood, center.municipality, center.postal_code)
    line2 = (center.city, center.state)
    return {
        "line1": ", ".join(p for p in line1 if p),
        "line2": ", ".join(p for p in line2 if p),
    }


def build_receta_context(visit_id, actor, *, permissions=None, roles=None):
    visit = get_visit_or_404(visit_id)
    prescription = VisitPrescription.objects.filter(id_visit=visit, is_active=True).first()
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

    general_indications = _general_indications(prescription.items)
    header = patient_header_or_409(visit)
    center = center_of(visit)
    folio = prescription.folio or ""
    issued = prescription.created_at.astimezone(PRINT_TZ) if prescription.created_at else None
    context = {
        "doc_title": "Receta médica",
        "folio": folio,
        "prescription_type": prescription.get_prescription_type_display(),
        "issued_date": fmt_date(issued),
        "issued": _date_boxes(fmt_date(issued)),
        # Hora de emision (RIS art. 29); la del pie es la de impresion.
        "issued_time": issued.strftime("%H:%M") if issued else "",
        "barcode_uri": code128_data_uri(folio, bar_height=18) if folio else "",
        "patient": header,
        "birth": _date_boxes(header.get("birth_date")),
        "expediente": llave_publica(visit)[0] or "",
        "doctor": doctor_info(consultation.doctor),
        "center_name": getattr(center, "name", "") or "",
        "center_address": _center_address(center),
        "clues": getattr(center, "code", "") or "",
        "consultorio": getattr(visit.consultorio, "name", "") if visit.consultorio else "",
        "general_indications": general_indications,
        # ope_param.ds_mreceta del legado, ahora parametro por centro.
        "legend": get_param("receta.leyenda", center_id=getattr(center, "pk", None), default=""),
        "health_message": get_param(
            "receta.mensaje_salud", center_id=getattr(center, "pk", None), default=""
        ),
        "microtext": _MICROTEXT,
        "sheets": build_sheets(
            rows, prescription.prescription_type, has_general_indications=bool(general_indications)
        ),
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
