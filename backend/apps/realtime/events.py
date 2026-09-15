from uuid import uuid4

from django.db import transaction

from apps.realtime.consumers.visits import VISITS_STREAM_GROUP
from apps.realtime.models import RealtimeSequence
from apps.realtime.publisher import RealtimePublishMetadata, RealtimePublisher

VISITS_STREAM_SEQUENCE_KEY = "visits.stream"

VISIT_EVENT_CREATED = "visit.created"
VISIT_EVENT_STATUS_CHANGED = "visit.status.changed"
VISIT_EVENT_CANCELLED = "visit.cancelled"
VISIT_EVENT_NO_SHOW = "visit.no_show"
VISIT_EVENT_DIAGNOSIS_SAVED = "visit.diagnosis.saved"
VISIT_EVENT_PRESCRIPTIONS_SAVED = "visit.prescriptions.saved"
VISIT_EVENT_CLOSED = "visit.closed"
VISIT_EVENT_PRESCRIPTION_AUTHORIZATION_REJECTED = "visit.prescription_authorization.rejected"


def _build_metadata(*, request_id, correlation_id):
    normalized_request_id = (request_id or "").strip() or str(uuid4())
    normalized_correlation_id = (correlation_id or "").strip() or normalized_request_id

    return RealtimePublishMetadata(
        request_id=normalized_request_id,
        correlation_id=normalized_correlation_id,
        sequence=_next_stream_sequence(VISITS_STREAM_SEQUENCE_KEY),
    )


def _next_stream_sequence(stream_key):
    with transaction.atomic():
        sequence_row, _ = RealtimeSequence.objects.select_for_update().get_or_create(
            stream_key=stream_key,
            defaults={"last_sequence": 0},
        )
        sequence_row.last_sequence += 1
        sequence_row.save(update_fields=["last_sequence", "fch_modf"])
        return sequence_row.last_sequence


def publish_visit_created(
    *,
    visit_id,
    status,
    request_id,
    correlation_id=None,
    publisher=None,
):
    realtime_publisher = publisher or RealtimePublisher()
    metadata = _build_metadata(request_id=request_id, correlation_id=correlation_id)

    return realtime_publisher.publish(
        group_names=[VISITS_STREAM_GROUP],
        event_type="visit.created",
        entity="visit",
        entity_id=visit_id,
        metadata=metadata,
        payload={
            "status": status,
        },
    )


def _publish_visit_event(
    *,
    event_type,
    visit_id,
    payload,
    request_id,
    correlation_id=None,
    publisher=None,
):
    realtime_publisher = publisher or RealtimePublisher()
    metadata = _build_metadata(request_id=request_id, correlation_id=correlation_id)

    return realtime_publisher.publish(
        group_names=[VISITS_STREAM_GROUP],
        event_type=event_type,
        entity="visit",
        entity_id=visit_id,
        metadata=metadata,
        payload=payload,
    )


def _build_status_payload(*, status, previous_status=None):
    payload = {"status": status}
    if previous_status is not None:
        payload["previousStatus"] = previous_status
    return payload


def publish_visit_created(
    *,
    visit_id,
    status,
    request_id,
    correlation_id=None,
    publisher=None,
):
    return _publish_visit_event(
        event_type=VISIT_EVENT_CREATED,
        visit_id=visit_id,
        payload=_build_status_payload(status=status),
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_status_changed(
    *,
    visit_id,
    status,
    previous_status=None,
    request_id,
    correlation_id=None,
    publisher=None,
):
    return _publish_visit_event(
        event_type=VISIT_EVENT_STATUS_CHANGED,
        visit_id=visit_id,
        payload=_build_status_payload(
            status=status,
            previous_status=previous_status,
        ),
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_cancelled(
    *,
    visit_id,
    status,
    previous_status=None,
    request_id,
    correlation_id=None,
    publisher=None,
):
    return _publish_visit_event(
        event_type=VISIT_EVENT_CANCELLED,
        visit_id=visit_id,
        payload=_build_status_payload(
            status=status,
            previous_status=previous_status,
        ),
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_no_show(
    *,
    visit_id,
    status,
    previous_status=None,
    request_id,
    correlation_id=None,
    publisher=None,
):
    return _publish_visit_event(
        event_type=VISIT_EVENT_NO_SHOW,
        visit_id=visit_id,
        payload=_build_status_payload(
            status=status,
            previous_status=previous_status,
        ),
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_diagnosis_saved(
    *,
    visit_id,
    status,
    primary_diagnosis,
    final_note,
    cie_code=None,
    request_id,
    correlation_id=None,
    publisher=None,
):
    payload = {
        "status": status,
        "primaryDiagnosis": primary_diagnosis,
        "finalNote": final_note,
    }
    if cie_code:
        payload["cieCode"] = cie_code

    return _publish_visit_event(
        event_type=VISIT_EVENT_DIAGNOSIS_SAVED,
        visit_id=visit_id,
        payload=payload,
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_prescriptions_saved(
    *,
    visit_id,
    status,
    items,
    request_id,
    correlation_id=None,
    publisher=None,
):
    return _publish_visit_event(
        event_type=VISIT_EVENT_PRESCRIPTIONS_SAVED,
        visit_id=visit_id,
        payload={
            "status": status,
            "items": list(items),
        },
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_prescription_authorization_rejected(
    *,
    visit_id,
    authorization_id,
    reason,
    request_id,
    correlation_id=None,
    publisher=None,
):
    """
    Avisa al medico que prescribio que su receta con medicamentos
    ESPECIAL/controlados fue rechazada -- sin esto no se entera salvo que
    vuelva a consultar la receta a mano.
    """
    return _publish_visit_event(
        event_type=VISIT_EVENT_PRESCRIPTION_AUTHORIZATION_REJECTED,
        visit_id=visit_id,
        payload={
            "authorizationId": authorization_id,
            "reason": reason,
        },
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )


def publish_visit_closed(
    *,
    visit_id,
    request_id,
    correlation_id=None,
    publisher=None,
):
    return _publish_visit_event(
        event_type=VISIT_EVENT_CLOSED,
        visit_id=visit_id,
        payload={},
        request_id=request_id,
        correlation_id=correlation_id,
        publisher=publisher,
    )
