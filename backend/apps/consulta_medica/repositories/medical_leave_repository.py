from django.utils import timezone

from apps.consulta_medica.models import MedicalLeave
from apps.consulta_medica.services.patient_link_service import for_patient
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp


class MedicalLeaveRepository:
    @staticmethod
    def get_active_for_consultation(consultation):
        return MedicalLeave.objects.filter(
            consultation=consultation, is_active=True,
            status=MedicalLeave.Status.EMITIDA,
        ).first()

    @staticmethod
    def get_active_overlap_for_patient(no_exp, pk_num, on_date):
        return (
            for_patient(
                MedicalLeave.objects.filter(
                    is_active=True, status=MedicalLeave.Status.EMITIDA, end_date__gte=on_date,
                ),
                no_exp, pk_num,
            )
            .order_by("-end_date")
            .first()
        )

    @staticmethod
    def create(
        *,
        consultation,
        no_exp,
        pk_num,
        leave_type,
        is_subsequent,
        days,
        start_date,
        end_date,
        folio,
        created_by_id=None,
        updated_by_id=None,
    ):
        return MedicalLeave.objects.create(
            consultation=consultation,
            no_exp=no_exp,
            pk_num=pk_num,
            leave_type=leave_type,
            is_subsequent=is_subsequent,
            days=days,
            start_date=start_date,
            end_date=end_date,
            folio=folio,
            created_by_id=created_by_id,
            updated_by_id=updated_by_id,
        )

    @staticmethod
    def list_for_patient(no_exp, pk_num):
        return (
            for_patient(MedicalLeave.objects.filter(is_active=True), no_exp, pk_num)
            .select_related("leave_type")
            .order_by("-start_date")
        )

    @staticmethod
    def list_report(fecha_inicio, fecha_fin, *, leave_type_id=None, no_exp=None):
        """
        Incapacidades/licencias cuya fecha de inicio cae en el rango dado --
        equivalente moderno de body-repincap.jsp del legado. Ver
        docs/architecture/legacy-reports-inventory.md.
        """
        queryset = (
            MedicalLeave.objects.filter(
                is_active=True,
                status=MedicalLeave.Status.EMITIDA,
                start_date__gte=fecha_inicio,
                start_date__lte=fecha_fin,
            )
            .select_related(
                "leave_type",
                "consultation",
                "consultation__id_visit",
                "consultation__doctor",
                "consultation__doctor__detalle",
            )
            .order_by("start_date")
        )
        if leave_type_id is not None:
            queryset = queryset.filter(leave_type_id=leave_type_id)
        if no_exp is not None:
            # Plan contraer la llave vieja: el expediente se busca en cns_paciente.
            queryset = queryset.filter(patient__no_exp=normalizar_no_exp(no_exp))
        return queryset

    @staticmethod
    def to_report_row(leave):
        visit = leave.consultation.id_visit
        doctor = leave.consultation.doctor
        doctor_detalle = getattr(doctor, "detalle", None)
        return {
            "id": leave.id_medical_leave,
            "folio": leave.folio,
            "noExp": leave.no_exp,
            "pkNum": leave.pk_num,
            "patientName": visit.nombre_paciente if visit else None,
            "doctorName": doctor_detalle.nombre_completo if doctor_detalle else None,
            "leaveTypeId": leave.leave_type_id,
            "leaveTypeName": leave.leave_type.name,
            "isSubsequent": leave.is_subsequent,
            "days": leave.days,
            "startDate": leave.start_date,
            "endDate": leave.end_date,
        }

    @staticmethod
    def to_contract(leave):
        return {
            "id": leave.id_medical_leave,
            "visitId": leave.consultation.id_visit_id,
            "folio": leave.folio,
            "leaveTypeId": leave.leave_type_id,
            "leaveTypeName": leave.leave_type.name,
            "isSubsequent": leave.is_subsequent,
            "days": leave.days,
            "startDate": leave.start_date,
            "endDate": leave.end_date,
            "isActive": leave.is_active,
            "status": leave.status,
            "createdAt": leave.created_at,
        }

    @staticmethod
    def list_active_for_consultation_for_update(consultation):
        """Incapacidades emitidas de la consulta, FOR UPDATE, orden fijo por pk.
        Solo dentro de transaction.atomic() (cascada de cancelacion de nota)."""
        return list(
            MedicalLeave.objects.select_for_update()
            .filter(consultation=consultation, is_active=True, status=MedicalLeave.Status.EMITIDA)
            .order_by("pk")
        )

    @staticmethod
    def cancel(leave, *, cancelled_by_id):
        """Baja LOGICA de la incapacidad (nunca DELETE). Libera el traslape."""
        leave.status = MedicalLeave.Status.CANCELADA
        leave.cancelled_at = timezone.now()
        leave.cancelled_by_id = cancelled_by_id
        leave.updated_by_id = cancelled_by_id
        leave.save(update_fields=[
            "status", "cancelled_at", "cancelled_by_id", "updated_by_id", "updated_at",
        ])
        return leave
