import datetime

from apps.administracion.models import CatClinica
from apps.cirugias.models import SurgeryCancellation, SurgeryDiagnosis, SurgerySchedule
from apps.medicos.identity import display_name as medico_display_name


def _clinic_name(clinic_id):
    if not clinic_id:
        return None
    clinic = CatClinica.objects.filter(pk=clinic_id).only("ds_clinica").first()
    return clinic.ds_clinica if clinic else None


class SurgeryRepository:
    @staticmethod
    def get_by_id(surgery_id):
        return SurgerySchedule.objects.filter(pk=surgery_id, is_active=True).first()

    @staticmethod
    def has_conflict(surgeon, scheduled_date, scheduled_time, duration_minutes, *, exclude_id=None):
        """
        Traslape de horario para el mismo medico en la misma fecha --
        equivalente moderno de vw_cirugias/existeTraslape del legado. Se
        compara en Python (no ExclusionConstraint) para no atar el modelo a
        un motor de base de datos especifico.
        """
        duration = duration_minutes or 30
        start = datetime.datetime.combine(scheduled_date, scheduled_time)
        end = start + datetime.timedelta(minutes=duration)

        candidates = SurgerySchedule.objects.filter(
            surgeon=surgeon,
            scheduled_date=scheduled_date,
            status=SurgerySchedule.Status.ACTIVA,
            is_active=True,
        )
        if exclude_id is not None:
            candidates = candidates.exclude(pk=exclude_id)

        for candidate in candidates:
            candidate_start = datetime.datetime.combine(
                candidate.scheduled_date, candidate.scheduled_time,
            )
            candidate_end = candidate_start + datetime.timedelta(
                minutes=candidate.duration_minutes or 30,
            )
            if start < candidate_end and candidate_start < end:
                return True
        return False

    @staticmethod
    def create(**fields):
        return SurgerySchedule.objects.create(**fields)

    @staticmethod
    def add_diagnosis(*, surgery, cie, created_by_id=None):
        return SurgeryDiagnosis.objects.create(
            surgery=surgery, cie=cie, created_by_id=created_by_id,
        )

    @staticmethod
    def cancel(surgery, *, reason, notes, updated_by_id=None):
        surgery.status = SurgerySchedule.Status.CANCELADA
        surgery.updated_by_id = updated_by_id
        surgery.save(update_fields=["status", "updated_by_id", "updated_at"])
        SurgeryCancellation.objects.create(
            surgery=surgery, reason=reason, notes=notes, created_by_id=updated_by_id,
        )
        return surgery

    @staticmethod
    def list_queryset(
        *,
        fecha_inicio=None,
        fecha_fin=None,
        surgeon_id=None,
        classification_id=None,
        status=None,
        no_exp=None,
    ):
        queryset = (
            SurgerySchedule.objects.filter(is_active=True)
            # origin_clinic_id NO se puede select_related: CatClinica vive
            # en la BD "expedientes" (ver routers.ExpedientesRouter), una
            # base de datos fisicamente distinta.
            .select_related("surgeon", "surgery_type", "classification")
            .prefetch_related("diagnoses__cie")
            .order_by("scheduled_date", "scheduled_time")
        )
        if fecha_inicio is not None:
            queryset = queryset.filter(scheduled_date__gte=fecha_inicio)
        if fecha_fin is not None:
            queryset = queryset.filter(scheduled_date__lte=fecha_fin)
        if surgeon_id is not None:
            queryset = queryset.filter(surgeon_id=surgeon_id)
        if classification_id is not None:
            queryset = queryset.filter(classification_id=classification_id)
        if status is not None:
            queryset = queryset.filter(status=status)
        if no_exp is not None:
            queryset = queryset.filter(no_exp=no_exp)
        return queryset

    @staticmethod
    def to_contract(surgery):
        return {
            "id": surgery.id,
            "folio": surgery.folio,
            "noExp": surgery.no_exp,
            "pkNum": surgery.pk_num,
            "surgeonId": surgery.surgeon_id,
            "surgeonName": medico_display_name(surgery.surgeon),
            "surgeryTypeId": surgery.surgery_type_id,
            "surgeryTypeName": surgery.surgery_type.name,
            "classificationId": surgery.classification_id,
            "classificationName": surgery.classification.name,
            "originClinicId": surgery.origin_clinic_id,
            "originClinicName": _clinic_name(surgery.origin_clinic_id),
            "scheduledDate": surgery.scheduled_date,
            "scheduledTime": surgery.scheduled_time,
            "durationMinutes": surgery.duration_minutes,
            "contactPhone": surgery.contact_phone,
            "description": surgery.description,
            "diagnosisText": surgery.diagnosis_text,
            "requirements": surgery.requirements,
            "status": surgery.status,
            "performedStatus": surgery.performed_status,
            "diagnoses": [
                {"id": d.id, "cieCode": d.cie_id, "cieName": d.cie.description}
                for d in surgery.diagnoses.all()
            ],
            "createdAt": surgery.created_at,
        }

    @staticmethod
    def to_report_row(surgery):
        return {
            "date": surgery.scheduled_date,
            "time": surgery.scheduled_time,
            "folio": surgery.folio,
            "noExp": surgery.no_exp,
            "pkNum": surgery.pk_num,
            "surgeonName": medico_display_name(surgery.surgeon),
            "surgeryTypeName": surgery.surgery_type.name,
            "classificationName": surgery.classification.name,
            "status": surgery.status,
            "performedStatus": surgery.performed_status,
        }
