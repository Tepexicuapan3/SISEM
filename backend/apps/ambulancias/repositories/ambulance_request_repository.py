from django.utils import timezone

from apps.administracion.models import CatClinica
from apps.ambulancias.models import AmbulanceRequest, AmbulanceRequestSchedule


def _clinic_name(clinic_id):
    if not clinic_id:
        return None
    clinic = CatClinica.objects.filter(pk=clinic_id).only("ds_clinica").first()
    return clinic.ds_clinica if clinic else None


class AmbulanceRequestRepository:
    @staticmethod
    def get_by_id(request_id):
        return AmbulanceRequest.objects.filter(pk=request_id, is_active=True).first()

    @staticmethod
    def create(**fields):
        return AmbulanceRequest.objects.create(**fields)

    @staticmethod
    def add_schedule(*, request, transfer_date, transfer_time, transfer_type, service_type, created_by_id=None):
        return AmbulanceRequestSchedule.objects.create(
            request=request,
            transfer_date=transfer_date,
            transfer_time=transfer_time,
            transfer_type=transfer_type,
            service_type=service_type,
            created_by_id=created_by_id,
        )

    @staticmethod
    def authorize(request, *, service_number, updated_by_id=None):
        request.authorization_status = AmbulanceRequest.AuthorizationStatus.AUTORIZADA
        request.service_number = service_number
        request.authorized_by_id = updated_by_id
        request.authorized_at = timezone.now()
        request.updated_by_id = updated_by_id
        request.save(
            update_fields=[
                "authorization_status", "service_number", "authorized_by_id",
                "authorized_at", "updated_by_id", "updated_at",
            ]
        )
        return request

    @staticmethod
    def reject(request, *, notes, updated_by_id=None):
        request.authorization_status = AmbulanceRequest.AuthorizationStatus.RECHAZADA
        request.rejection_notes = notes
        request.authorized_by_id = updated_by_id
        request.authorized_at = timezone.now()
        request.updated_by_id = updated_by_id
        request.save(
            update_fields=[
                "authorization_status", "rejection_notes", "authorized_by_id",
                "authorized_at", "updated_by_id", "updated_at",
            ]
        )
        return request

    @staticmethod
    def cancel(request, *, updated_by_id=None):
        request.status = AmbulanceRequest.Status.BAJA
        request.updated_by_id = updated_by_id
        request.save(update_fields=["status", "updated_by_id", "updated_at"])
        return request

    @staticmethod
    def list_queryset(
        *,
        fecha_inicio=None,
        fecha_fin=None,
        authorization_status=None,
        status=None,
        no_exp=None,
    ):
        queryset = (
            AmbulanceRequest.objects.filter(is_active=True)
            # requesting_clinic_id NO se puede select_related: CatClinica
            # vive en la BD "expedientes" (ver routers.ExpedientesRouter).
            .select_related("reason", "destination")
            .prefetch_related("schedules__transfer_type", "schedules__service_type")
            .order_by("-created_at")
        )
        if fecha_inicio is not None:
            queryset = queryset.filter(created_at__date__gte=fecha_inicio)
        if fecha_fin is not None:
            queryset = queryset.filter(created_at__date__lte=fecha_fin)
        if authorization_status is not None:
            queryset = queryset.filter(authorization_status=authorization_status)
        if status is not None:
            queryset = queryset.filter(status=status)
        if no_exp is not None:
            queryset = queryset.filter(no_exp=no_exp)
        return queryset

    @staticmethod
    def to_contract(request):
        return {
            "id": request.id,
            "folio": request.folio,
            "noExp": request.no_exp,
            "pkNum": request.pk_num,
            "requestingClinicId": request.requesting_clinic_id,
            "requestingClinicName": _clinic_name(request.requesting_clinic_id),
            "requestedByName": request.requested_by_name,
            "socialWorkNotes": request.social_work_notes,
            "reasonId": request.reason_id,
            "reasonName": request.reason.name,
            "reasonNotes": request.reason_notes,
            "diagnosisText": request.diagnosis_text,
            "originStreet": request.origin_street,
            "originZip": request.origin_zip,
            "originNeighborhood": request.origin_neighborhood,
            "originBorough": request.origin_borough,
            "originPhone": request.origin_phone,
            "originReference": request.origin_reference,
            "destinationId": request.destination_id,
            "destinationName": request.destination.name,
            "status": request.status,
            "authorizationStatus": request.authorization_status,
            "authorizedById": request.authorized_by_id,
            "authorizedAt": request.authorized_at,
            "serviceNumber": request.service_number,
            "rejectionNotes": request.rejection_notes,
            "schedules": [
                {
                    "id": s.id,
                    "transferDate": s.transfer_date,
                    "transferTime": s.transfer_time,
                    "transferTypeId": s.transfer_type_id,
                    "transferTypeName": s.transfer_type.name,
                    "serviceTypeId": s.service_type_id,
                    "serviceTypeName": s.service_type.name,
                }
                for s in request.schedules.all()
                if s.status == "activa"
            ],
            "createdAt": request.created_at,
        }

    @staticmethod
    def to_report_row(request):
        first_schedule = next(iter(request.schedules.all()), None)
        return {
            "date": request.created_at,
            "folio": request.folio,
            "noExp": request.no_exp,
            "pkNum": request.pk_num,
            "requestingClinicName": _clinic_name(request.requesting_clinic_id),
            "reasonName": request.reason.name,
            "destinationName": request.destination.name,
            "transferDate": first_schedule.transfer_date if first_schedule else None,
            "status": request.status,
            "authorizationStatus": request.authorization_status,
            "serviceNumber": request.service_number,
        }
