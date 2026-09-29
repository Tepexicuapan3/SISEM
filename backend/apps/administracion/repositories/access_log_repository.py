"""
Lectura de BITACORA_ACCESO (tabla propia `bitacora_acceso`, ver
models.bitacora_acceso). Solo lectura.

`eventType` se deriva de `restringidos`: "diagnostico_restringido" cuando la
lectura oculto diagnosticos sensibles, "acceso" en cualquier otro caso.
"""
from apps.administracion.models import BitacoraAcceso

EVENT_TYPES = ("acceso", "diagnostico_restringido")


class AccessLogRepository:
    @staticmethod
    def list_events(
        *,
        page,
        page_size,
        event_type=None,
        action=None,
        fecha_inicio=None,
        fecha_fin=None,
        no_exp=None,
        pk_num=None,
        section=None,
        actor_username=None,
    ):
        queryset = BitacoraAcceso.objects.select_related("usuario__detalle")

        if event_type == "diagnostico_restringido":
            queryset = queryset.filter(restringidos__gt=0)
        elif event_type == "acceso":
            queryset = queryset.filter(restringidos=0)
        if action:
            queryset = queryset.filter(accion=action)
        if fecha_inicio:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_fin)
        if no_exp:
            queryset = queryset.filter(no_exp=str(no_exp))
        if pk_num is not None:
            queryset = queryset.filter(tp_paciente=pk_num)
        if section:
            queryset = queryset.filter(recurso=section)
        if actor_username:
            queryset = queryset.filter(cd_usuario__icontains=actor_username)

        queryset = queryset.order_by("-fecha_hora", "-id")
        total = queryset.count()
        start = (page - 1) * page_size
        entries = list(queryset[start:start + page_size])

        return {
            "items": [AccessLogRepository._serialize(entry) for entry in entries],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
        }

    @staticmethod
    def _serialize(entry):
        detalle = getattr(entry.usuario, "detalle", None) if entry.usuario_id else None
        return {
            "id": entry.id,
            "occurredAt": entry.fecha_hora.isoformat() if entry.fecha_hora else None,
            "eventType": "diagnostico_restringido" if entry.restringidos else "acceso",
            "action": entry.accion,
            "actorId": entry.usuario_id,
            "actorUsername": entry.cd_usuario,
            "actorName": detalle.nombre_completo if detalle else None,
            "noExp": entry.no_exp,
            "pkNum": entry.tp_paciente,
            "section": entry.recurso,
            "redactedCount": entry.restringidos or None,
            "ipAddress": entry.ip_origen,
            "endpoint": entry.endpoint,
        }
