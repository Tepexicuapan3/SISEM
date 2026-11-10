"""
Reprogramar una cita (Fase B): en una sola transacción se cancela la anterior
con el motivo tipificado "Reagendada" (libera su horario) y se agenda la nueva
con ``agendar_cita``, mismas reglas que una cita nueva (vigencia, clínica,
consultorio familiar, horario libre, topes). Si la nueva no se puede, la
anterior queda como estaba.

La nueva queda enlazada a la anterior (``CitaMedica.reprogramada_de``, uno a
uno) y la bitácora de las dos lo dice: "Reprogramada" en la cancelación y
"Reprogramada desde CIT-…" en el alta.

Solo se reprograma una cita agendada o confirmada sin ficha: si ya tiene
ficha, primero se cancela la ficha en la bandeja.
"""

from django.db import transaction

from apps.catalogos.models import MotivoCita
from apps.consulta_medica.services.paciente_entrada import llave_publica
from apps.recepcion.models import CanalMovimiento, CitaMedica, EstatusCita, Visit
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.asistencia_cita_service import ESTATUS_PENDIENTE
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.agendar_cita_usecase import agendar_cita

MOTIVO_REPROGRAMADA = "Reagendada"


def reprogramar_cita(
    *,
    cita_id,
    fecha_hora,
    created_by_id,
    operador,
    request,
    medico_id=None,
    consultorio_id=None,
    motivo_detalle=None,
    excepcion_consultorio_familiar=None,
    canal=CanalMovimiento.RECEPCION,
) -> dict:
    """
    Devuelve la cita nueva. ``medico_id`` vacío: el mismo médico (y su
    consultorio, salvo que se indique otro). La autorización (permiso y
    alcance por centro) la hace quien llama.
    """
    with transaction.atomic():
        anterior = CitaMedica.objects.select_for_update().filter(pk=cita_id).first()
        if anterior is None:
            raise VisitDomainError("CITA_NOT_FOUND", "Cita no encontrada.", 404)
        if anterior.estatus not in ESTATUS_PENDIENTE:
            raise VisitDomainError(
                "CITA_NO_REPROGRAMABLE", "Solo se reprograma una cita agendada o confirmada.", 409,
            )
        if Visit.objects.filter(appointment_id=anterior.folio).exists():
            raise VisitDomainError(
                "CITA_CON_FICHA",
                "La cita ya tiene ficha: cancela la ficha en la bandeja antes de reprogramarla.",
                409,
            )

        mismo_medico = medico_id is None or medico_id == anterior.medico_id
        detalle = (motivo_detalle or "").strip()
        # Primero se cancela: libera el horario, así sirve también para
        # moverla dentro del mismo día o al mismo horario.
        CitasRepository.update_estatus(
            anterior,
            EstatusCita.CANCELADA,
            motivo_cancelacion=MotivoCita.objects.filter(name=MOTIVO_REPROGRAMADA, is_active=True).first(),
            motivo_detalle=f"Reprogramada: {detalle}" if detalle else "Reprogramada",
            changed_by_id=created_by_id,
            canal=canal,
        )
        no_exp, pk_num = llave_publica(anterior)
        return agendar_cita(
            no_exp=no_exp,
            pk_num=pk_num,
            id_paciente=anterior.patient_id,
            medico_id=anterior.medico_id if mismo_medico else medico_id,
            consultorio_id=consultorio_id or (anterior.consultorio_id if mismo_medico else None),
            fecha_hora=fecha_hora,
            duracion_min=anterior.duracion_min,
            servicio_tipo=anterior.servicio_tipo,
            motivo=anterior.motivo,
            notas=anterior.notas,
            excepcion_consultorio_familiar=excepcion_consultorio_familiar,
            created_by_id=created_by_id,
            operador=operador,
            request=request,
            canal=canal,
            reprogramada_de=anterior,
        )
