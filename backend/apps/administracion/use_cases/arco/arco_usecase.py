"""
Casos de uso de Solicitudes ARCO (change `solicitudes-arco`). Ver docstring
de `SolicitudArco` para el alcance y las reglas de inmutabilidad.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.administracion.models import SolicitudArco

# Transiciones permitidas. `recibida -> procedente|improcedente` directo es
# valido: una solicitud simple puede resolverse sin pasar por `en_proceso`.
_ALLOWED_TRANSITIONS = {
    SolicitudArco.Estatus.RECIBIDA: {
        SolicitudArco.Estatus.EN_PROCESO,
        SolicitudArco.Estatus.PROCEDENTE,
        SolicitudArco.Estatus.IMPROCEDENTE,
    },
    SolicitudArco.Estatus.EN_PROCESO: {
        SolicitudArco.Estatus.PROCEDENTE,
        SolicitudArco.Estatus.IMPROCEDENTE,
    },
}


class ArcoError(Exception):
    def __init__(self, code, message, status_code, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def add_business_days(start_date, days):
    """Suma `days` dias habiles (lunes a viernes) a `start_date`. No descuenta
    feriados oficiales: si juridico lo exige, este es el unico punto a
    cambiar."""
    current = start_date
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _snapshot(solicitud):
    return {
        "estatus": solicitud.estatus,
        "respuesta": solicitud.respuesta,
    }


def create_solicitud(data, *, actor, audit_hook):
    fecha_recepcion = data.get("receivedDate") or timezone.localdate()

    with transaction.atomic():
        solicitud = SolicitudArco.objects.create(
            # Folio temporal unico: el definitivo depende del PK.
            folio=uuid.uuid4().hex[:20],
            tipo=data["type"],
            no_exp=data["noExp"].strip(),
            pk_num=data.get("pkNum", 0),
            solicitante_nombre=data["requesterName"].strip(),
            solicitante_relacion=data.get("requesterRelation") or SolicitudArco.Relacion.TITULAR,
            solicitante_correo=data.get("requesterEmail") or None,
            solicitante_telefono=data.get("requesterPhone") or None,
            descripcion=data["description"].strip(),
            folio_unidad_transparencia=(data.get("transparencyFolio") or "").strip() or None,
            fecha_recepcion=fecha_recepcion,
            fecha_limite=add_business_days(fecha_recepcion, settings.ARCO_PLAZO_DIAS_HABILES),
            registrada_por=actor,
        )
        solicitud.folio = f"ARCO-{fecha_recepcion.year}-{solicitud.id_solicitud:06d}"
        solicitud.save(update_fields=["folio"])

        audit_hook(
            action="ArcoRequestCreated",
            resource_id=solicitud.id_solicitud,
            datos_antes=None,
            datos_despues={**_snapshot(solicitud), "folio": solicitud.folio, "tipo": solicitud.tipo},
        )

    return serialize_solicitud(solicitud)


def change_status(solicitud_id, data, *, actor, audit_hook):
    target = data["status"]
    respuesta = (data.get("response") or "").strip()

    with transaction.atomic():
        solicitud = (
            SolicitudArco.objects.select_for_update().filter(id_solicitud=solicitud_id).first()
        )
        if solicitud is None:
            raise ArcoError("NOT_FOUND", "Solicitud ARCO no encontrada", 404)

        if solicitud.is_final:
            raise ArcoError(
                "ARCO_ALREADY_RESOLVED",
                "La solicitud ya fue resuelta y no puede modificarse",
                409,
            )

        if target not in _ALLOWED_TRANSITIONS.get(solicitud.estatus, set()):
            raise ArcoError(
                "INVALID_TRANSITION",
                f"No se puede pasar de '{solicitud.estatus}' a '{target}'",
                409,
            )

        if target in SolicitudArco.ESTATUS_FINALES and not respuesta:
            raise ArcoError(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                422,
                details={"response": ["La respuesta es obligatoria para resolver la solicitud."]},
            )

        antes = _snapshot(solicitud)
        solicitud.estatus = target
        update_fields = ["estatus", "fch_modf"]
        if target in SolicitudArco.ESTATUS_FINALES:
            solicitud.respuesta = respuesta
            solicitud.resuelta_por = actor
            solicitud.fch_resolucion = timezone.now()
            solicitud.fecha_respuesta = timezone.localdate()
            update_fields += ["respuesta", "resuelta_por", "fch_resolucion", "fecha_respuesta"]
        solicitud.save(update_fields=update_fields)

        audit_hook(
            action="ArcoRequestStatusChanged",
            resource_id=solicitud.id_solicitud,
            datos_antes=antes,
            datos_despues=_snapshot(solicitud),
        )

    return serialize_solicitud(solicitud)


def get_solicitud(solicitud_id):
    solicitud = (
        SolicitudArco.objects.select_related("registrada_por", "resuelta_por")
        .filter(id_solicitud=solicitud_id)
        .first()
    )
    if solicitud is None:
        raise ArcoError("NOT_FOUND", "Solicitud ARCO no encontrada", 404)
    return serialize_solicitud(solicitud)


def list_solicitudes(*, page, page_size, estatus=None, tipo=None, no_exp=None, overdue=False):
    queryset = SolicitudArco.objects.select_related("registrada_por", "resuelta_por")
    if estatus:
        queryset = queryset.filter(estatus=estatus)
    if tipo:
        queryset = queryset.filter(tipo=tipo)
    if no_exp:
        queryset = queryset.filter(no_exp=no_exp)
    if overdue:
        queryset = queryset.exclude(estatus__in=SolicitudArco.ESTATUS_FINALES).filter(
            fecha_limite__lt=timezone.localdate()
        )
    queryset = queryset.order_by("-fch_alta", "-id_solicitud")

    total = queryset.count()
    start = (page - 1) * page_size
    return {
        "items": [serialize_solicitud(item) for item in queryset[start:start + page_size]],
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": (total + page_size - 1) // page_size,
    }


def serialize_solicitud(solicitud):
    today = timezone.localdate()
    return {
        "id": solicitud.id_solicitud,
        "folio": solicitud.folio,
        "type": solicitud.tipo,
        "status": solicitud.estatus,
        "noExp": solicitud.no_exp,
        "pkNum": solicitud.pk_num,
        "requesterName": solicitud.solicitante_nombre,
        "requesterRelation": solicitud.solicitante_relacion,
        "requesterEmail": solicitud.solicitante_correo,
        "requesterPhone": solicitud.solicitante_telefono,
        "description": solicitud.descripcion,
        "transparencyFolio": solicitud.folio_unidad_transparencia,
        "receivedDate": solicitud.fecha_recepcion.isoformat(),
        "dueDate": solicitud.fecha_limite.isoformat(),
        "isOverdue": not solicitud.is_final and solicitud.fecha_limite < today,
        "response": solicitud.respuesta,
        "resolvedAt": solicitud.fch_resolucion.isoformat() if solicitud.fch_resolucion else None,
        "responseDate": solicitud.fecha_respuesta.isoformat() if solicitud.fecha_respuesta else None,
        "registeredBy": _user_ref(solicitud.registrada_por),
        "resolvedBy": _user_ref(solicitud.resuelta_por),
        "createdAt": solicitud.fch_alta.isoformat() if solicitud.fch_alta else None,
    }


def _user_ref(user):
    if user is None:
        return None
    return {"id": user.id_usuario, "username": user.usuario}
