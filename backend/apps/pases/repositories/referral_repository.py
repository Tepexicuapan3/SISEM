from apps.pases.models import Referral, ReferralStudyDetail

_STUDY_TYPES = {Referral.ReferralType.LABORATORIO, Referral.ReferralType.GABINETE}


class ReferralRepository:
    @staticmethod
    def get_by_id(referral_id):
        return Referral.objects.filter(pk=referral_id, is_active=True).first()

    @staticmethod
    def get_active_by_consultation_and_type(consultation, referral_type):
        return Referral.objects.filter(
            consultation=consultation,
            referral_type=referral_type,
            status=Referral.Status.ACTIVO,
            is_active=True,
        ).first()

    @staticmethod
    def create(
        *,
        consultation,
        no_exp,
        pk_num,
        referral_type,
        destination_center=None,
        specialty=None,
        requested_care=None,
        visit_type=None,
        folio,
        created_by_id=None,
        updated_by_id=None,
    ):
        return Referral.objects.create(
            consultation=consultation,
            no_exp=no_exp,
            pk_num=pk_num,
            referral_type=referral_type,
            destination_center=destination_center,
            specialty=specialty,
            requested_care=requested_care,
            visit_type=visit_type,
            folio=folio,
            created_by_id=created_by_id,
            updated_by_id=updated_by_id,
        )

    @staticmethod
    def add_study_detail(*, referral, study_type, created_by_id=None, updated_by_id=None):
        return ReferralStudyDetail.objects.create(
            referral=referral,
            study_type=study_type,
            created_by_id=created_by_id,
            updated_by_id=updated_by_id,
        )

    @staticmethod
    def cancel(referral, *, cancellation_reason, updated_by_id=None):
        referral.status = Referral.Status.CANCELADO
        referral.cancellation_reason = cancellation_reason
        referral.updated_by_id = updated_by_id
        referral.save(
            update_fields=["status", "cancellation_reason", "updated_by_id", "updated_at"]
        )
        return referral

    @staticmethod
    def list_for_patient(no_exp, pk_num):
        return (
            Referral.objects.filter(no_exp=no_exp, pk_num=pk_num, is_active=True)
            .select_related("destination_center", "specialty", "cancellation_reason")
            .prefetch_related("study_details__study_type")
            .order_by("-created_at")
        )

    @staticmethod
    def list_report(fecha_inicio, fecha_fin, *, referral_type=None, status=None, no_exp=None):
        """
        Pases emitidos en un rango de fechas -- equivalente moderno de
        body-repases.jsp/body-repingresados.jsp/body-rephospital.jsp del
        legado. Ver docs/architecture/legacy-reports-inventory.md.
        """
        queryset = (
            Referral.objects.filter(
                is_active=True,
                created_at__date__gte=fecha_inicio,
                created_at__date__lte=fecha_fin,
            )
            .select_related(
                "destination_center",
                "specialty",
                "consultation",
                "consultation__id_visit",
                "consultation__doctor",
                "consultation__doctor__detalle",
            )
            .order_by("created_at")
        )
        if referral_type is not None:
            queryset = queryset.filter(referral_type=referral_type)
        if status is not None:
            queryset = queryset.filter(status=status)
        if no_exp is not None:
            queryset = queryset.filter(no_exp=no_exp)
        return queryset

    @staticmethod
    def to_report_row(referral):
        visit = referral.consultation.id_visit
        doctor = referral.consultation.doctor
        doctor_detalle = getattr(doctor, "detalle", None)
        return {
            "id": referral.id_referral,
            "date": referral.created_at,
            "folio": referral.folio,
            "referralType": referral.referral_type,
            "noExp": referral.no_exp,
            "pkNum": referral.pk_num,
            "patientName": visit.nombre_paciente if visit else None,
            "doctorName": doctor_detalle.nombre_completo if doctor_detalle else None,
            "destinationCenterName": (
                referral.destination_center.name if referral.destination_center_id else None
            ),
            "specialtyName": referral.specialty.name if referral.specialty_id else None,
            "visitType": referral.visit_type,
            "status": referral.status,
        }

    @staticmethod
    def to_contract(referral):
        studies = []
        if referral.referral_type in _STUDY_TYPES:
            studies = [
                {
                    "id": detail.id_referral_study,
                    "studyTypeId": detail.study_type_id,
                    "studyTypeName": detail.study_type.name,
                    "costApproved": detail.cost_approved,
                    "validUntil": detail.valid_until,
                    "status": detail.status,
                }
                for detail in referral.study_details.all()
                if detail.is_active
            ]

        return {
            "id": referral.id_referral,
            "visitId": referral.consultation.id_visit_id,
            "noExp": referral.no_exp,
            "pkNum": referral.pk_num,
            "referralType": referral.referral_type,
            "destinationCenterId": referral.destination_center_id,
            "destinationCenterName": (
                referral.destination_center.name if referral.destination_center_id else None
            ),
            "specialtyId": referral.specialty_id,
            "specialtyName": referral.specialty.name if referral.specialty_id else None,
            "requestedCare": referral.requested_care,
            "visitType": referral.visit_type,
            "folio": referral.folio,
            "status": referral.status,
            "cancellationReasonId": referral.cancellation_reason_id,
            "studies": studies,
            "isActive": referral.is_active,
            "createdAt": referral.created_at,
        }
