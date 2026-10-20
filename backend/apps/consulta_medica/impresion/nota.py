"""
apps/consulta_medica/impresion/nota.py
==========================================
Builder de la Nota medica para el modulo ``impresion`` (solo lectura).

Reglas (R5): solo nota cerrada o cancelada; la cancelada se imprime con
marca de agua CANCELADA y muestra los documentos tal como quedaron tras la
cascada. Los diagnosticos sensibles se redactan con los permisos de quien
imprime, igual que en pantalla.
"""

from zoneinfo import ZoneInfo

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
from apps.consulta_medica.models import VisitDiagnosis
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted
from apps.impresion.registry import PrintContext

PRINT_TZ = ZoneInfo("America/Mexico_City")

# (etiqueta, atributo de VisitConsultation). Las secciones vacias se omiten.
NOTE_SECTIONS = (
    ("Padecimiento actual", "current_illness"),
    ("Interrogatorio por aparatos y sistemas", "systems_review"),
    ("Subjetivo", "subjective"),
    ("Objetivo", "objective"),
    ("Análisis", "assessment"),
    ("Plan", "plan"),
    ("Plan diagnóstico", "diagnostic_plan"),
    ("Plan terapéutico", "therapeutic_plan"),
    ("Nota final", "final_note"),
)


def _sections(consultation):
    rows = []
    for label, attr in NOTE_SECTIONS:
        text = (getattr(consultation, attr, None) or "").strip()
        if text:
            rows.append({"label": label, "text": text})
    return rows


def _vitals(visit):
    try:
        vitals = visit.vital_signs
    except Exception:
        return None
    if vitals is None:
        return None
    ta = ""
    if vitals.blood_pressure_systolic and vitals.blood_pressure_diastolic:
        ta = f"{vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}"
    return {
        "peso": vitals.weight_kg,
        "talla": vitals.height_cm,
        "imc": vitals.bmi,
        "ta": ta,
        "temperatura": vitals.temperature_c or "",
        "fc": vitals.heart_rate_bpm or "",
        "fr": vitals.respiratory_rate_bpm or "",
        "spo2": vitals.oxygen_saturation_pct or "",
        "glucosa": vitals.glucosa_capilar_mgdl or "",
        "cintura": vitals.waist_circumference_cm or "",
    }


def _diagnoses(consultation, cancelled, permissions, roles):
    rows = []
    cie = consultation.cie
    code, description, text, _ = redact_cie_if_restricted(
        code=getattr(cie, "code", None),
        description=getattr(cie, "description", "") or "",
        permissions=permissions,
        roles=roles,
        linked_text=consultation.primary_diagnosis,
    )
    rows.append({"kind": "Principal", "code": code or "", "description": description, "notes": text or ""})

    secondary = VisitDiagnosis.objects.select_related("cie").filter(consultation=consultation)
    if not cancelled:
        secondary = secondary.filter(status=VisitDiagnosis.Status.ACTIVO)
    for dx in secondary.order_by("pk"):
        code, description, notes, _ = redact_cie_if_restricted(
            code=dx.cie.code,
            description=dx.cie.description,
            permissions=permissions,
            roles=roles,
            linked_text=dx.notes,
        )
        rows.append({"kind": "Secundario", "code": code or "", "description": description, "notes": notes or ""})
    return rows


def _referrals(consultation, cancelled):
    qs = consultation.referrals.select_related("specialty", "destination_center").filter(is_active=True)
    if not cancelled:
        qs = qs.filter(status="activo")
    return [
        {
            "folio": r.folio,
            "type": r.get_referral_type_display(),
            "specialty": getattr(r.specialty, "name", "") or "",
            "destination": getattr(r.destination_center, "name", "") or "",
            "requested_care": r.requested_care or "",
            "status": r.get_status_display(),
        }
        for r in qs.order_by("pk")
    ]


def _medical_leaves(consultation, cancelled):
    qs = consultation.medical_leaves.select_related("leave_type").filter(is_active=True)
    if not cancelled:
        qs = qs.filter(status="emitida")
    return [
        {
            "folio": leave.folio,
            "type": getattr(leave.leave_type, "name", "") or "",
            "days": leave.days,
            "start": fmt_date(leave.start_date),
            "end": fmt_date(leave.end_date),
            "status": leave.get_status_display(),
        }
        for leave in qs.order_by("pk")
    ]


def _addenda(consultation):
    return [
        {"date": fmt_date(a.created_at.astimezone(PRINT_TZ)), "text": a.text}
        for a in consultation.addenda.all()
    ]


def build_nota_context(visit_id, actor, *, permissions=None, roles=None):
    visit = get_visit_or_404(visit_id)
    consultation = get_consultation(visit)
    if consultation is None:
        raise not_printable("La visita no tiene nota medica.")
    cancelled = is_note_cancelled(visit, consultation)
    if not cancelled and visit.status != VISIT_CLOSED:
        raise not_printable("La nota solo se imprime con la consulta cerrada.")

    header = patient_header_or_409(visit)
    center = center_of(visit)
    attended = consultation.created_at.astimezone(PRINT_TZ) if consultation.created_at else None
    context = {
        "doc_title": "Nota médica",
        "folio": visit.folio,
        "attended_date": fmt_date(attended),
        "service": visit.get_service_type_display(),
        "patient": header,
        "expediente": visit.no_exp or "",
        "doctor": doctor_info(consultation.doctor),
        "center_name": getattr(center, "name", "") or "",
        "consultorio": getattr(visit.consultorio, "name", "") if visit.consultorio else "",
        "morbidity": consultation.get_morbidity_display() if consultation.morbidity else "",
        "follow_up_date": fmt_date(consultation.follow_up_date),
        "vitals": _vitals(visit),
        "sections": _sections(consultation),
        "diagnoses": _diagnoses(consultation, cancelled, permissions or [], roles or []),
        "referrals": _referrals(consultation, cancelled),
        "medical_leaves": _medical_leaves(consultation, cancelled),
        "addenda": _addenda(consultation),
        "is_cancelled": cancelled,
    }
    return PrintContext(
        context=context,
        no_exp=visit.no_exp,
        pk_num=visit.pk_num,
        folio=visit.folio or "",
        filename=f"nota_{visit.folio}.pdf",
        is_cancelled=cancelled,
        center_id=getattr(center, "pk", None),
        legacy_cd_clinica=getattr(center, "legacy_cd_clinica", None),
        source=consultation,
    )
