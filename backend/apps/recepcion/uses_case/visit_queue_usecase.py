from django.db import transaction

import logging

from apps.administracion.use_cases.expedientes.buscar_expediente import buscar_expediente
from apps.authentication.services.authorization_service import has_capability
from apps.medicos.identity import medico_id_for_usuario
from apps.recepcion.models import HorarioDisponible, Visit
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_state_machine_usecase import (
    ROLE_RECEPCION,
    transition_visit_state,
)

logger = logging.getLogger(__name__)

_ACTIVE_VISIT_STATUSES = (
    "en_espera", "en_somatometria", "lista_para_doctor", "en_consulta",
)

RECEPCION_WRITE_CAPABILITY = "flow.recepcion.queue.write"
VISIT_QUEUE_READ_CAPABILITY = "flow.visits.queue.read"
SOMATOMETRIA_QUEUE_READ_CAPABILITY = "flow.somatometria.queue.read"
DOCTOR_QUEUE_READ_CAPABILITY = "flow.doctor.queue.read"


# ── Autorización ──────────────────────────────────────────────────────────────

def ensure_recepcion_role(roles, permissions=None):
    del roles
    if has_capability(permissions or [], RECEPCION_WRITE_CAPABILITY):
        return
    raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso para esta acción.", 403)


def ensure_visit_queue_access(roles, permissions):
    del roles
    if has_capability(permissions or [], VISIT_QUEUE_READ_CAPABILITY):
        return
    raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso para esta acción.", 403)


def resolve_vitals_visibility(permissions) -> bool:
    """
    Narrowing de contrato (D3, somatometria-modulo-integral): decide si
    `GET /visits` (LIST) devuelve los VALORES numericos de signos vitales
    o solo el estado narrowed ({hasVitals, capturedAt, reusedFrom}).

    Enfermeria/somatometria (`flow.somatometria.queue.read`) y medico
    (`flow.doctor.queue.read`) siguen viendo metricas completas;
    cualquier otro caller (ej. recepcion, que solo tiene
    `recepcion:fichas:*:create`) recibe unicamente el estado.

    Solo afecta el LIST -- el detalle de una visita individual
    (`get_by_id` / `change_visit_status`) no pasa por aca y sigue en
    `include_vitals_values=True` siempre.

    Rollback de emergencia (1 linea): en `VisitsView.get`, reemplazar
    `include_vitals_values=resolve_vitals_visibility(...)` por
    `include_vitals_values=True` fijo.
    """
    permissions = permissions or []
    return (
        has_capability(permissions, SOMATOMETRIA_QUEUE_READ_CAPABILITY)
        or has_capability(permissions, DOCTOR_QUEUE_READ_CAPABILITY)
    )


# ── Pacientes ─────────────────────────────────────────────────────────────────

def _build_member(source: dict, pk_num: int, no_exp_key: str) -> dict:
    """Construye el dict de un miembro a partir de una fila de SERMED."""
    return {
        "noExp":      source[no_exp_key],
        "pkNum":      pk_num,
        "nombre":     f"{source['DS_PATERNO']} {source['DS_MATERNO']} {source['DS_NOMBRE']}".strip(),
        "edad":       source.get("EDAD"),
        "fechaNac":   str(source["FE_NAC"]) if source.get("FE_NAC") else None,
        "parentesco": source.get("CD_PARENTESCO", "TRABAJADOR"),
        "estatus":    source.get("ESTATUS", ""),
        "cdClinica":  source.get("CD_CLINICA"),
    }


def lookup_patient(no_exp: str, historico: bool = False) -> dict:
    """
    Busca el titular y sus derechohabientes por expediente.

    historico=False (default): solo retorna miembros ACTIVOS — usado en check-in.
    historico=True: retorna todos sin filtrar estatus — usado en vista de fichas.
    """
    if not no_exp:
        raise VisitDomainError("VALIDATION_ERROR", "El número de expediente es requerido.", 400)

    resultado  = buscar_expediente(no_exp)
    empleados  = resultado.get("empleados",  [])
    familiares = resultado.get("familiares", [])

    if not empleados:
        raise VisitDomainError("PATIENT_NOT_FOUND", "Expediente no encontrado.", 404)

    emp = empleados[0]

    # Titular
    es_activo_titular = emp.get("ESTATUS") == "ACTIVO"
    titular = _build_member(emp, 0, "NO_EXP") if (historico or es_activo_titular) else None

    # Derechohabientes
    dependientes = [
        _build_member(fam, fam["PK_NUM"], "NO_EXPF")
        for fam in familiares
        if historico or fam.get("ESTATUS") == "ACTIVO"
    ]

    if not historico and titular is None and not dependientes:
        raise VisitDomainError(
            "PATIENT_NO_SERVICE",
            "El trabajador está de baja y no hay derechohabientes con vigencia activa.",
            404,
        )

    return {"titular": titular, "dependientes": dependientes}


# ── Visitas ───────────────────────────────────────────────────────────────────

def _check_and_reserve_slot(doctor_id: int, medico_id: int | None, hora_consulta, fecha_consulta=None) -> None:
    """
    Verifica que el médico no tenga ya una ficha activa en ese horario/fecha
    y marca el slot de HorarioDisponible como ocupado.
    Usa SELECT FOR UPDATE para prevenir race conditions.
    fecha_consulta: date object o None (usa today como fallback).

    ``doctor_id`` (espacio usuario, FK a SyUsuario -- filtra/crea ``Visit``)
    y ``medico_id`` (espacio médico, FK a CatMedico -- filtra/crea
    ``HorarioDisponible``) son DOS ids distintos desde el cambio
    medico-pk-independiente (R1). ``medico_id`` puede ser None si el
    ``doctor_id`` no tiene perfil de médico en el catálogo -- en ese caso no
    hay agenda (HorarioDisponible) que reservar, se salta ese bloque.
    """
    from django.utils import timezone

    fecha = fecha_consulta or timezone.localtime(timezone.now()).date()

    with transaction.atomic():
        slot = None
        if medico_id is not None:
            slot = (
                HorarioDisponible.objects
                .select_for_update()
                .filter(medico_id=medico_id, fecha=fecha, hora=hora_consulta)
                .first()
            )

            if slot and not slot.disponible:
                raise VisitDomainError(
                    "VISIT_SLOT_CONFLICT",
                    "El horario seleccionado ya está ocupado.",
                    409,
                )

        if Visit.objects.filter(
            doctor_id=doctor_id,
            hora_consulta=hora_consulta,
            fecha_consulta=fecha,
            fch_baja__isnull=True,
            status__in=_ACTIVE_VISIT_STATUSES,
        ).exists():
            raise VisitDomainError(
                "VISIT_SLOT_CONFLICT",
                "El médico ya tiene una ficha para ese horario.",
                409,
            )

        if medico_id is None:
            # Sin perfil de médico en el catálogo: no hay agenda que
            # reservar (HorarioDisponible es del espacio médico). El
            # chequeo de conflicto sobre Visit.doctor_id de arriba ya cubre
            # la prevención de doble-ficha para este usuario.
            return

        if slot:
            slot.disponible = False
            slot.save(update_fields=["disponible"])
        else:
            HorarioDisponible.objects.create(
                medico_id=medico_id,
                fecha=fecha,
                hora=hora_consulta,
                disponible=False,
            )


def create_visit(
    no_exp: str,
    pk_num: int = 0,
    nombre_paciente: str | None = None,
    arrival_type: str = Visit.ArrivalType.WALK_IN,
    service_type: str = Visit.ServiceType.MEDICINA_GENERAL,
    appointment_id: str | None = None,
    doctor_id: int | None = None,
    medico_id: int | None = None,
    consultorio_id: int | None = None,
    tipo_cita_id: int | None = None,
    notes: str | None = None,
    hora_consulta=None,
    fecha_consulta=None,
    created_by_id: int | None = None,
) -> dict:
    """
    ``doctor_id``: id de usuario (espacio SyUsuario) -- FK real de
    ``Visit.doctor``. ``medico_id``: PK surrogate de CatMedico (espacio
    médico) -- usado para reservar el slot de ``HorarioDisponible``. Si el
    caller ya conoce ambos (p.ej. ``qr_checkin_usecase``, que parte de una
    ``CitaMedica`` con ``medico_id`` real), debe pasar los dos explícitos.
    Si solo llega ``doctor_id`` (check-in manual walk-in), se traduce acá.
    """
    if VisitRepository.exists_open_visit_for_patient(no_exp, pk_num):
        raise VisitDomainError(
            "VISIT_DUPLICATE_SUBMIT",
            "Ya existe una visita abierta para este paciente.",
            409,
        )

    if medico_id is None:
        medico_id = medico_id_for_usuario(doctor_id)

    # Validar conflicto solo cuando se envió hora explícita
    if doctor_id and hora_consulta:
        _check_and_reserve_slot(doctor_id, medico_id, hora_consulta, fecha_consulta=fecha_consulta)

    # Calcular número de ficha y turno al momento del registro
    num_ficha, turno_nombre = _calcular_num_ficha()

    visit = VisitRepository.create(
        no_exp=no_exp,
        pk_num=pk_num,
        nombre_paciente=nombre_paciente,
        arrival_type=arrival_type,
        service_type=service_type,
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        consultorio_id=consultorio_id,
        tipo_cita_id=tipo_cita_id,
        notes=notes,
        hora_consulta=hora_consulta,
        fecha_consulta=fecha_consulta,
        num_ficha=num_ficha,
        turno_nombre=turno_nombre,
        created_by_id=created_by_id,
    )
    # Registrar el estado inicial en el log de auditoría
    VisitRepository.log_status_change(
        visit=visit,
        from_status=None,
        to_status="en_espera",
        changed_by_id=created_by_id,
        notes="Check-in inicial",
    )
    return VisitRepository.to_contract(visit)


def _calcular_num_ficha() -> tuple[int, str]:
    """
    Determina el número secuencial de ficha para el turno actual del día.
    Retorna (num_ficha, turno_nombre).
    Usa SELECT COUNT con el rango horario del turno → un solo query, O(1).
    """
    from datetime import date, datetime
    from django.utils import timezone
    from apps.recepcion.models import TurnoFichaConfig, Visit

    hora_actual = timezone.localtime(timezone.now()).time()
    turno = (
        TurnoFichaConfig.objects
        .filter(is_active=True, hora_inicio__lte=hora_actual, hora_fin__gt=hora_actual)
        .first()
    )

    if not turno:
        # Sin turno configurado: usar conteo total del día como fallback
        hoy = timezone.localtime(timezone.now()).date()
        inicio = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
        fin    = timezone.make_aware(datetime.combine(hoy, datetime.max.time()))
        count  = Visit.objects.filter(fch_alta__gte=inicio, fch_alta__lte=fin).count()
        return count + 1, ""

    hoy       = timezone.localtime(timezone.now()).date()
    inicio_dt = timezone.make_aware(datetime.combine(hoy, turno.hora_inicio))
    fin_dt    = timezone.make_aware(datetime.combine(hoy, turno.hora_fin))
    count     = Visit.objects.filter(fch_alta__gte=inicio_dt, fch_alta__lt=fin_dt).count()

    return count + 1, turno.nombre


def _resolver_hora_medico(medico_id: int):
    """
    Obtiene la hora_inicio del horario activo del médico para hoy.

    NOTA: sin caller activo en el código actual (verificado, F4-19) -- se
    corrige igual el nombre del parámetro (espacio médico, FK real de
    RelMedicoConsultorio.medico) y se deja de tragar errores en silencio,
    para que si algún día se vuelve a usar, quede resuelto correctamente
    desde el día uno en vez de reintroducir la conflación doctor_id/medico_id (R1).
    """
    from datetime import date
    from django.db.models import Q
    try:
        from apps.medicos.models import RelMedicoConsultorio
        hoy     = date.today()
        dia_map = {0: "LUNES", 1: "MARTES", 2: "MIERCOLES", 3: "JUEVES",
                   4: "VIERNES", 5: "SABADO", 6: "DOMINGO"}
        dia     = dia_map[hoy.weekday()]
        rmc = (
            RelMedicoConsultorio.objects
            .prefetch_related("horarios")
            .filter(medico_id=medico_id, is_active=True, fecha_inicio__lte=hoy)
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
            .first()
        )
        if not rmc:
            return None
        horario = rmc.horarios.filter(dia_semana=dia).first()
        return horario.hora_inicio if horario else None
    except Exception:
        logger.warning(
            "Error resolviendo hora de consultorio para medico_id=%s", medico_id, exc_info=True
        )
        return None


def list_visits(
    page: int,
    page_size: int,
    status_filter: str | None = None,
    date_filter=None,
    doctor_id: int | None = None,
    consultorio_id: int | None = None,
    centro_id: int | None = None,
    service_type: str | None = None,
    no_exp: str | None = None,
    fecha_desde=None,
    fecha_hasta=None,
    folio: str | None = None,
    q: str | None = None,
    pk_num: int | None = None,
    *,
    include_vitals_values: bool = True,
) -> dict:
    visits, total, total_pages, doctor_nombres, cita_fechas = VisitRepository.list_paginated(
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        date_filter=date_filter,
        doctor_id=doctor_id,
        consultorio_id=consultorio_id,
        centro_id=centro_id,
        service_type=service_type,
        no_exp=no_exp,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        folio=folio,
        q=q,
        pk_num=pk_num,
    )
    return {
        "items":      [
            VisitRepository.to_contract(
                v, doctor_nombres, cita_fechas,
                include_vitals_values=include_vitals_values,
            )
            for v in visits
        ],
        "page":       page,
        "pageSize":   page_size,
        "total":      total,
        "totalPages": total_pages,
    }


def change_visit_status(
    visit_id: int,
    target_status: str,
    changed_by_id: int | None = None,
    motivo_cancelacion=None,
    motivo_detalle: str | None = None,
) -> dict:
    """
    ``motivo_cancelacion``: instancia (o PK) de ``catalogos.MotivoCita`` --
    catálogo tipificado exigido por la máquina de estados para cancelar
    (ver visit_state_machine_usecase). ``motivo_detalle`` es el texto libre
    complementario opcional.

    Todo el flujo lectura→validación→escritura corre DENTRO de un único
    ``transaction.atomic()`` con el lock (``select_for_update``) tomado
    ANTES de leer el estatus a transicionar -- mismo patrón que
    ``portal_citas.cancelar_cita_usecase.cancelar_cita`` -- para evitar una
    condición de carrera si dos requests concurrentes (doble click/doble
    pestaña) transicionan la misma visita al mismo tiempo.
    """
    with transaction.atomic():
        visit = VisitRepository.get_for_update(visit_id)
        if not visit:
            raise VisitDomainError("VISIT_NOT_FOUND", "Visita no encontrada.", 404)

        previous_status = visit.status
        next_state      = transition_visit_state(
            previous_status, target_status, ROLE_RECEPCION, motivo=motivo_cancelacion,
        )
        # Solo persistimos motivo_cancelacion/motivo_detalle cuando la
        # transicion es a "cancelada" -- las demas transiciones (no_show,
        # en_somatometria) no aceptan/usan motivo, aunque llegue en el payload.
        visit = VisitRepository.update_status(
            visit,
            next_state,
            motivo_cancelacion=motivo_cancelacion if next_state == "cancelada" else None,
            motivo_detalle=motivo_detalle if next_state == "cancelada" else None,
        )

        # Log de auditoría NOM-024
        status_log = VisitRepository.log_status_change(
            visit=visit,
            from_status=previous_status,
            to_status=next_state,
            changed_by_id=changed_by_id,
        )

        # `visit` fue obtenida con `get_for_update` (sin la anotacion
        # `en_somatometria_at` de `get_by_id`), asi que no ve todavia esta
        # transicion. Si la transicion actual ES hacia `en_somatometria`,
        # parcheamos el valor en memoria para que `to_contract` no dispare
        # una query de fallback innecesaria.
        if next_state == "en_somatometria":
            visit.en_somatometria_at = status_log.changed_at

        # Liberar el slot si la visita se cancela o marca como no-show --
        # dentro de la misma transacción que el cambio de estatus.
        if next_state in ("cancelada", "no_show") and visit.doctor_id and visit.hora_consulta:
            from django.utils import timezone
            medico_id = medico_id_for_usuario(visit.doctor_id)
            if medico_id is None:
                # El usuario que atendió no tiene (o ya no tiene) perfil de
                # médico en el catálogo -- no hay HorarioDisponible que
                # liberar en ese espacio. Antes de este fix se liberaba con
                # `medico_id=visit.doctor_id` directo (R1: conflación de
                # ids), lo que podía liberar el slot de OTRO médico.
                logger.warning(
                    "No se pudo traducir doctor_id=%s a medico_id -- no se libera slot "
                    "(visit_id=%s).",
                    visit.doctor_id, visit_id,
                )
            else:
                fecha_slot = visit.fecha_consulta or timezone.localtime(timezone.now()).date()
                HorarioDisponible.objects.filter(
                    medico_id=medico_id,
                    fecha=fecha_slot,
                    hora=visit.hora_consulta,
                    disponible=False,
                    cita__isnull=True,  # solo libera slots de fichas, no de CitaMedica formal
                ).update(disponible=True)

    return VisitRepository.to_contract(visit)


def get_visit_status_log(visit_id: int) -> list[dict]:
    """Retorna el historial de estados de una visita con nombres de usuario resueltos."""
    logs = VisitRepository.get_status_log(visit_id)
    if not logs:
        return []

    user_ids = {log.changed_by_id for log in logs if log.changed_by_id}
    user_nombres: dict[int, str] = {}
    if user_ids:
        from apps.authentication.models import DetUsuario
        dets = DetUsuario.objects.filter(id_usuario_id__in=user_ids)
        user_nombres = {d.id_usuario_id: d.nombre_completo for d in dets}

    return [VisitRepository.status_log_to_contract(log, user_nombres) for log in logs]
