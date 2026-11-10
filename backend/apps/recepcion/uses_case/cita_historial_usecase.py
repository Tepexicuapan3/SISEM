"""
Historial de una cita: su bitácora NOM-024 (``CitaEstatusLog``), del alta a
cada cambio de estatus, con el nombre de quien hizo cada movimiento. Sin
usuario (``changed_by_id`` vacío) es el paciente desde el portal o una tarea
automática.
"""

from apps.authentication.models import DetUsuario
from apps.recepcion.models import CitaEstatusLog, CitaMedica


def _contrato(log: CitaEstatusLog, nombres: dict) -> dict:
    return {
        "id":              log.id,
        "fromStatus":      log.from_status,
        "toStatus":        log.to_status,
        "changedById":     log.changed_by_id,
        "changedByNombre": nombres.get(log.changed_by_id),
        "changedAt":       log.changed_at.isoformat() if log.changed_at else None,
        "notes":           log.notes,
        "canal":           log.canal,
    }


def get_cita_historial(cita: CitaMedica) -> list[dict]:
    """``cita`` ya validada contra el alcance de quien consulta."""
    logs = list(CitaEstatusLog.objects.filter(cita=cita).order_by("changed_at", "id"))
    ids = {log.changed_by_id for log in logs if log.changed_by_id}
    nombres = {
        d.id_usuario_id: d.nombre_completo for d in DetUsuario.objects.filter(id_usuario_id__in=ids)
    } if ids else {}
    return [_contrato(log, nombres) for log in logs]
