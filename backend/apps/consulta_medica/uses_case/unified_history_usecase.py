"""
Piezas de la historia clinica unificada que no son registros permanentes
1:N: notas historicas (solo lectura), exploracion fisica por consulta,
catalogos clinicos y estado de alergias.
"""
from django.db import transaction
from django.utils import timezone

from apps.catalogos.models import (
    CatEstadoPieza,
    CatHabito,
    CatPiezaDental,
    CatRegionCorporal,
    CatTipoAlergia,
    Parentesco,
)
from apps.consulta_medica.models import (
    Allergy,
    HistoricalNote,
    LegacyVitalSigns,
    PhysicalExamFinding,
    VisitConsultation,
)
from apps.consulta_medica.repositories.allergy_repository import AllergyRepository
from apps.recepcion.services.errors import VisitDomainError

from .consultation_usecase import ensure_doctor_role


# ── Notas historicas (solo lectura) ──────────────────────────────────────────

def _decimal_or_none(value):
    return str(value) if value is not None else None


def _legacy_vitals_contract(vitals):
    return {
        "id": vitals.id_legacy_vitals,
        "specialty": vitals.specialty,
        "measuredOn": vitals.measured_on.isoformat() if vitals.measured_on else None,
        "weightKg": _decimal_or_none(vitals.weight_kg),
        "heightCm": _decimal_or_none(vitals.height_cm),
        "bloodPressureSystolic": vitals.blood_pressure_systolic,
        "bloodPressureDiastolic": vitals.blood_pressure_diastolic,
        "heartRateBpm": vitals.heart_rate_bpm,
        "temperatureC": _decimal_or_none(vitals.temperature_c),
        "respiratoryRateBpm": vitals.respiratory_rate_bpm,
        "bmi": _decimal_or_none(vitals.bmi),
        "rawText": vitals.raw_text,
    }


def list_historical_notes(no_exp, pk_num, roles, permissions=None, *, section=None, specialty=None):
    ensure_doctor_role(roles, permissions)
    notes = HistoricalNote.objects.filter(no_exp=no_exp, pk_num=pk_num)
    if section:
        notes = notes.filter(section=section)
    if specialty:
        notes = notes.filter(specialty=specialty)
    notes = notes.order_by("section", "noted_on", "id_historical_note")
    legacy_vitals = LegacyVitalSigns.objects.none()
    if section in (None, HistoricalNote.Section.VITAL_SIGNS):
        legacy_vitals = LegacyVitalSigns.objects.filter(no_exp=no_exp, pk_num=pk_num)
        if specialty:
            legacy_vitals = legacy_vitals.filter(specialty=specialty)
    return {
        "legacyVitals": [_legacy_vitals_contract(vitals) for vitals in legacy_vitals],
        "items": [
            {
                "id": note.id_historical_note,
                "section": note.section,
                "sectionLabel": note.get_section_display(),
                "specialty": note.specialty,
                "notedOn": note.noted_on.isoformat() if note.noted_on else None,
                "author": note.author,
                "content": note.content,
                "origin": note.origin,
            }
            for note in notes
        ]
    }


# ── Exploracion fisica por consulta ──────────────────────────────────────────

def _consultation_for_visit(visit_id):
    consultation = (
        VisitConsultation.objects.select_related("id_visit")
        .filter(id_visit_id=visit_id, is_active=True)
        .first()
    )
    if consultation is None:
        raise VisitDomainError("CONSULTATION_NOT_FOUND", "La visita no tiene consulta iniciada.", 404)
    return consultation


def _finding_contract(finding):
    return {
        "id": finding.id_finding,
        "regionId": finding.region_id,
        "regionCode": finding.region.code,
        "regionName": finding.region.name,
        "isNormal": finding.is_normal,
        "finding": finding.finding,
        "updatedAt": finding.updated_at,
    }


def get_physical_exam(visit_id, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    consultation = _consultation_for_visit(visit_id)
    findings = consultation.physical_exam_findings.select_related("region").order_by("region__order")
    return {
        "visitId": visit_id,
        "editable": consultation.id_visit.status == "en_consulta",
        "items": [_finding_contract(finding) for finding in findings],
    }


def save_physical_exam(visit_id, roles, findings, actor_id, permissions=None, *, audit_hook):
    """
    Guarda la exploracion completa de la consulta (una fila por region). Solo
    mientras la visita esta `en_consulta`: despues del cierre la nota es
    inmutable y las correcciones van por ConsultationAddendum.
    """
    ensure_doctor_role(roles, permissions)
    consultation = _consultation_for_visit(visit_id)
    if consultation.id_visit.status != "en_consulta":
        raise VisitDomainError(
            "VISIT_STATE_INVALID",
            "La exploracion solo se edita con la consulta abierta. Usa una nota de aclaracion.",
            409,
        )

    region_ids = [item["regionId"] for item in findings]
    if len(region_ids) != len(set(region_ids)):
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"findings": ["Cada region solo puede aparecer una vez."]},
        )
    valid_regions = set(
        CatRegionCorporal.objects.filter(pk__in=region_ids, is_active=True).values_list("pk", flat=True)
    )
    invalid = sorted(set(region_ids) - valid_regions)
    if invalid:
        raise VisitDomainError(
            "VALIDATION_ERROR", "Hay errores en el formulario", 422,
            details={"findings": [f"Region invalida: {invalid}."]},
        )

    with transaction.atomic():
        before = {
            finding.region_id: finding.is_normal
            for finding in consultation.physical_exam_findings.all()
        }
        consultation.physical_exam_findings.exclude(region_id__in=region_ids).delete()
        for item in findings:
            PhysicalExamFinding.objects.update_or_create(
                consultation=consultation,
                region_id=item["regionId"],
                defaults={
                    "is_normal": item["isNormal"],
                    "finding": (item.get("finding") or "").strip() or None,
                    "updated_by_id": actor_id,
                    "created_by_id": actor_id,
                },
            )
        audit_hook(
            resource_id=consultation.id_consultation,
            datos_antes={"regions": {str(k): v for k, v in sorted(before.items())}},
            datos_despues={
                "regions": {str(item["regionId"]): item["isNormal"] for item in findings},
            },
        )

    return get_physical_exam(visit_id, roles, permissions)


# ── Catalogos clinicos ───────────────────────────────────────────────────────

def get_clinical_catalogs(roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    return {
        "allergyTypes": [
            {"id": item.id, "code": item.code, "name": item.name}
            for item in CatTipoAlergia.objects.filter(is_active=True).order_by("id")
        ],
        "habits": [
            {"id": item.id, "code": item.code, "name": item.name}
            for item in CatHabito.objects.filter(is_active=True).order_by("name")
        ],
        "bodyRegions": [
            {"id": item.id, "code": item.code, "name": item.name}
            for item in CatRegionCorporal.objects.filter(is_active=True).order_by("order", "name")
        ],
        "toothStates": [
            {"id": item.id, "code": item.code, "name": item.name, "dmftComponent": item.dmft_component}
            for item in CatEstadoPieza.objects.filter(is_active=True).order_by("name")
        ],
        "teeth": [
            {"fdi": item.fdi, "name": item.name, "dentition": item.dentition, "quadrant": item.quadrant}
            for item in CatPiezaDental.objects.order_by("fdi")
        ],
        "relationships": [
            {"id": item.id, "name": item.name}
            for item in Parentesco.objects.filter(is_active=True).order_by("name")
        ],
    }


# ── Estado de alergias ───────────────────────────────────────────────────────

def change_allergy_status(no_exp, pk_num, allergy_id, roles, *, status, reason, actor_id,
                          permissions=None, audit_hook):
    """
    Documento (decision pendiente, adoptada): cualquier medico puede marcar
    una alergia como resuelta o capturada por error, con motivo obligatorio y
    registro en bitacora. "Error" la saca de las alertas (is_active=False);
    "resuelta" la deja visible como historia pero fuera del cruce con recetas.
    """
    ensure_doctor_role(roles, permissions)
    allergy = Allergy.objects.filter(pk=allergy_id, no_exp=no_exp, pk_num=pk_num).first()
    if allergy is None or allergy.status == Allergy.Status.ENTERED_IN_ERROR:
        raise VisitDomainError("ALLERGY_NOT_FOUND", "Alergia no encontrada.", 404)
    if allergy.status == status:
        raise VisitDomainError("ALLERGY_STATUS_UNCHANGED", "La alergia ya tiene ese estado.", 409)

    with transaction.atomic():
        previous = allergy.status
        allergy.status = status
        allergy.status_reason = reason.strip()
        allergy.updated_by_id = actor_id
        if status == Allergy.Status.ENTERED_IN_ERROR:
            allergy.is_active = False
            allergy.deleted_at = timezone.now()
            allergy.deleted_by_id = actor_id
        allergy.save()
        audit_hook(
            resource_id=allergy.id_allergy,
            datos_antes={"status": previous},
            datos_despues={"status": status, "reason": allergy.status_reason},
            strict=True,
        )

    return AllergyRepository.to_contract(allergy)
