"""
Mi jornada del medico: las consultas que cerro hoy, con el estado de su receta.

La consulta cerrada sale de la cola (solo muestra visitas abiertas); desde aqui
el medico la sigue viendo e imprime la receta sin depender del aviso de cierre
ni ir al expediente (NOM-024: disponibilidad). Solo sus consultas y solo las de
hoy: lo historico vive en el expediente.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.consulta_medica.models import PrescriptionAuthorization
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.repositories.medical_leave_repository import MedicalLeaveRepository
from apps.consulta_medica.repositories.prescription_authorization_repository import (
    PrescriptionAuthorizationRepository,
)
from apps.consulta_medica.repositories.prescription_item_repository import PrescriptionItemRepository
from apps.consulta_medica.repositories.prescription_repository import PrescriptionRepository
from apps.consulta_medica.services.paciente_entrada import llave_publica
# Pases es otro dominio: se lee por su repositorio (mismo camino que la cancelacion de notas).
from apps.pases.repositories.referral_repository import ReferralRepository

from .consultation_usecase import ensure_doctor_role

MX_TZ = ZoneInfo("America/Mexico_City")

# Misma regla que la impresion de la receta (impresion/receta.py).
_BLOCKING_AUTH = {
    PrescriptionAuthorization.Status.PENDIENTE,
    PrescriptionAuthorization.Status.RECHAZADA,
}


def _day_bounds(day):
    start = datetime.combine(day, time.min, tzinfo=MX_TZ)
    return start, start + timedelta(days=1)


def _prescription_contract(folio, summary, authorization):
    count = summary["count"] if summary else 0
    return {
        "folio": folio,
        "medicationsCount": count,
        "hasControlled": bool(summary and summary["controlled"]),
        "authorization": authorization,
        "printable": count > 0 and (authorization or {}).get("status") not in _BLOCKING_AUTH,
    }


def list_attended_today(actor_id, roles, permissions=None, *, today=None):
    ensure_doctor_role(roles, permissions)
    day = today or timezone.now().astimezone(MX_TZ).date()
    consultations = list(ConsultationRepository.closed_by_doctor_between(actor_id, *_day_bounds(day)))

    visit_ids = [c.id_visit_id for c in consultations]
    folios = PrescriptionRepository.active_folios_by_visit(visit_ids)
    summaries = PrescriptionItemRepository.active_summary_by_visit(visit_ids)
    authorizations = PrescriptionAuthorizationRepository.latest_by_visit(visit_ids)
    consultation_ids = [c.pk for c in consultations]
    leaves = MedicalLeaveRepository.active_by_consultation(consultation_ids)
    referrals = ReferralRepository.active_by_consultation(consultation_ids)

    items = []
    for consultation in consultations:
        visit = consultation.id_visit
        no_exp, pk_num = llave_publica(visit)
        items.append({
            "visitId": visit.id_visit,
            "folio": visit.folio,
            "nombrePaciente": visit.nombre_paciente or "",
            "noExp": no_exp or "",
            "pkNum": pk_num,
            "attendedAt": consultation.updated_at.isoformat() if consultation.updated_at else None,
            "prescription": (
                _prescription_contract(
                    folios[visit.id_visit], summaries.get(visit.id_visit), authorizations.get(visit.id_visit),
                )
                if visit.id_visit in folios
                else None
            ),
            # Lo demas que salio de la consulta: la nota cerrada siempre se puede reimprimir.
            "documents": {
                "notePrintable": True,
                "medicalLeave": leaves.get(consultation.pk),
                "referrals": referrals.get(consultation.pk, []),
                "followUpDate": consultation.follow_up_date.isoformat() if consultation.follow_up_date else None,
            },
        })
    return {"items": items, "total": len(items)}
