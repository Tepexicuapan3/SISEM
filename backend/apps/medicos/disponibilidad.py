"""
Servicio de disponibilidad médica.
Determina qué médicos están disponibles en una fecha/centro dado
y qué consultorio/horario les corresponde considerando coberturas.
"""

from datetime import date, datetime, timedelta
from django.db.models import Q


_DIA_MAP = {
    0: "LUNES",
    1: "MARTES",
    2: "MIERCOLES",
    3: "JUEVES",
    4: "VIERNES",
    5: "SABADO",
    6: "DOMINGO",
}


def dia_semana(fecha: date) -> str:
    return _DIA_MAP[fecha.weekday()]


def get_asignacion_activa(medico, fecha: date):
    """
    Devuelve la asignación de consultorio activa para ese médico en esa fecha.
    Prioridad: cobertura activa > asignación regular.
    Retorna dict con keys: consultorio_id, centro_id, origen ('COBERTURA'|'REGULAR'), horarios
    """
    from apps.medicos.models import RelMedicoCobertura, RelMedicoConsultorio

    # 1. Buscar cobertura activa
    cobertura = (
        RelMedicoCobertura.objects
        .select_related("consultorio", "centro")
        .filter(
            medico_suplente=medico,
            is_active=True,
            fecha_inicio__lte=fecha,
            fecha_fin__gte=fecha,
        )
        .first()
    )
    if cobertura:
        horarios = {
            h.dia_semana: {"hora_inicio": h.hora_inicio, "hora_fin": h.hora_fin}
            for h in cobertura.horarios.all()
        }
        return {
            "consultorio_id":     cobertura.consultorio_id,
            "consultorio_numero": cobertura.consultorio.numero if cobertura.consultorio else None,
            "consultorio_nombre": cobertura.consultorio.name   if cobertura.consultorio else None,
            "centro_id":          cobertura.centro_id,
            "origen":             "COBERTURA",
            "horarios":           horarios,
        }

    # 2. Asignación regular
    asignacion = (
        RelMedicoConsultorio.objects
        .select_related("consultorio__id_center")
        .filter(
            medico=medico,
            is_active=True,
            fecha_inicio__lte=fecha,
        )
        .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))
        .first()
    )
    if asignacion:
        horarios = {
            h.dia_semana: {
                "hora_inicio": h.hora_inicio,
                "hora_fin": h.hora_fin,
                "intervalo_cita_min": h.intervalo_cita_min,
            }
            for h in asignacion.horarios.all()
        }
        consultorio = asignacion.consultorio
        return {
            "consultorio_id":     asignacion.consultorio_id,
            "consultorio_numero": consultorio.numero       if consultorio else None,
            "consultorio_nombre": consultorio.name         if consultorio else None,
            "centro_id":          consultorio.id_center_id if consultorio else None,
            "origen":             "REGULAR",
            "horarios":           horarios,
        }

    return None


def get_excepcion_dia(medico, fecha: date):
    """Devuelve la excepción activa para esa fecha (si existe)."""
    from apps.medicos.models import RelMedicoExcepcion

    return (
        RelMedicoExcepcion.objects
        .filter(
            medico=medico,
            is_active=True,
            fecha_inicio__lte=fecha,
            fecha_fin__gte=fecha,
        )
        .first()
    )


def get_disponibilidad_medico(medico, fecha: date) -> dict:
    """
    Calcula la disponibilidad completa de un médico para una fecha.
    """
    from apps.medicos.models import RelMedicoConsultorioHorario

    if medico.estatus_medico != "ACTIVO":
        return {"disponible": False, "motivo": medico.estatus_medico}

    asignacion = get_asignacion_activa(medico, fecha)
    if not asignacion:
        return {"disponible": False, "motivo": "SIN_CONSULTORIO"}

    dia = dia_semana(fecha)
    horario_dia = asignacion["horarios"].get(dia)
    if not horario_dia:
        return {"disponible": False, "motivo": "NO_TRABAJA_ESE_DIA"}

    excepcion = get_excepcion_dia(medico, fecha)
    if excepcion and excepcion.hora_inicio is None:
        return {"disponible": False, "motivo": excepcion.tipo, "excepcion_id": excepcion.id}

    return {
        "disponible":        True,
        "consultorioId":     asignacion["consultorio_id"],
        "consultorioNumero": asignacion["consultorio_numero"],
        "consultorioNombre": asignacion["consultorio_nombre"],
        "centroId":          asignacion["centro_id"],
        "origen":            asignacion["origen"],
        "horaInicio":        str(horario_dia["hora_inicio"]),
        "horaFin":           str(horario_dia["hora_fin"]),
        "intervaloCitaMin":  horario_dia.get("intervalo_cita_min", 20),
        "excepcionParcial": {
            "horaInicio": str(excepcion.hora_inicio),
            "horaFin":    str(excepcion.hora_fin),
            "tipo":       excepcion.tipo,
        } if excepcion else None,
    }


def get_medicos_disponibles(centro_id: int, fecha: date) -> list:
    """
    Lista médicos disponibles en un centro para una fecha.
    Usado por recepción y citas.
    """
    from apps.medicos.models import CatMedico, RelMedicoCentro
    from django.db.models import Q

    # Médicos adscritos activos en el centro. medico_id acá YA es la PK de
    # CatMedico (RelMedicoCentro.medico es FK a CatMedico -- espacio
    # médico), así que se filtra por `pk__in`, no por `id_usuario_id__in`
    # (R1: antes de este fix mezclaba espacios de ids -- por casualidad
    # coincidían numéricamente mientras id_usuario era la PK).
    medico_ids = RelMedicoCentro.objects.filter(
        centro_id=centro_id,
        is_active=True,
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).values_list("medico_id", flat=True)

    medicos = (
        CatMedico.objects
        .select_related("id_usuario__detalle")
        .filter(pk__in=medico_ids, estatus_medico="ACTIVO")
    )

    import logging
    from apps.medicos.identity import display_name
    _log = logging.getLogger(__name__)

    resultado = []
    for medico in medicos:
        try:
            disp = get_disponibilidad_medico(medico, fecha)
        except Exception:
            _log.exception("Error calculando disponibilidad para médico %s", medico.id)
            continue
        if disp["disponible"]:
            resultado.append({
                "medicoId":       medico.id,
                "usuarioId":      medico.id_usuario_id,
                "nombreCompleto": display_name(medico),
                "servicio":       medico.servicio,
                "tipoMedico":     medico.tipo_medico,
                **disp,
            })

    return resultado

