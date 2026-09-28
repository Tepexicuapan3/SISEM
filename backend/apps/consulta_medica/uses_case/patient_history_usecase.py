from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.legacy_consultation_repository import (
    LegacyConsultationRepository,
)
from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted

from .consultation_usecase import ensure_doctor_role


def _doctor_name(doctor):
    if doctor is None:
        return None
    detalle = getattr(doctor, "detalle", None)
    return detalle.nombre_completo if detalle else None


def _consultation_to_history_item(consultation, permissions):
    visit = consultation.id_visit
    prescription = PrescriptionRepository.get_by_visit(visit)

    # Diagnosticos sensibles (change `diagnosticos-sensibles`): se redacta
    # `cieCode`/`cieDescription` Y `primaryDiagnosis` (texto libre pero
    # deterministicamente ligado a este CIE) cuando el actor no tiene el
    # permiso requerido -- el resto de la consulta (fecha, medico,
    # finalNote/SOAP) se sirve normal, decision del usuario de no ocultar
    # el registro completo.
    cie_code, cie_description, primary_diagnosis, restricted = redact_cie_if_restricted(
        code=consultation.cie_id,
        description=consultation.cie.description if consultation.cie else None,
        permissions=permissions,
        linked_text=consultation.primary_diagnosis,
    )

    return {
        "visitId": visit.id_visit,
        "date": visit.fecha_consulta,
        "doctorId": consultation.doctor_id,
        "doctorName": _doctor_name(consultation.doctor),
        "serviceType": visit.service_type,
        "primaryDiagnosis": primary_diagnosis,
        "cieCode": cie_code,
        "cieDescription": cie_description,
        "finalNote": consultation.final_note,
        "prescriptionItems": list(prescription.items or []) if prescription else [],
        "restricted": restricted,
    }


def get_patient_consultations_history(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)

    consultations = ConsultationRepository.list_for_patient(no_exp, pk_num)
    items = [_consultation_to_history_item(c, permissions) for c in consultations]
    redacted_visit_ids = [item["visitId"] for item in items if item["restricted"]]

    return {
        "items": items,
        "total": len(items),
        "redactedVisitIds": redacted_visit_ids,
    }


def get_patient_legacy_consultations_history(no_exp, pk_num, roles, permissions=None):
    """
    Historial de notas del legado (previas a SIRES) -- archivo de solo
    lectura, no participa del flujo operativo (ver docstring de
    LegacyConsultationRecord). `totalCount` es el conteo REAL en la base
    (puede ser mayor a `len(items)` si se recorto por _MAX_RESULTS del
    repository).
    """
    ensure_doctor_role(roles, permissions)

    records = LegacyConsultationRepository.list_for_patient(no_exp, pk_num)
    items = [LegacyConsultationRepository.to_contract(r) for r in records]
    total_count = LegacyConsultationRepository.count_for_patient(no_exp, pk_num)

    return {
        "items": items,
        "total": len(items),
        "totalCount": total_count,
    }
