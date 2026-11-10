"""
Agendar una cita: un solo camino para recepción (``POST /citas``) y para el
médico que deja el seguimiento al cerrar la consulta.

Si la cita es para hoy y no es del portal, su ficha sale en ese momento
(``materializar_fichas_usecase``); si no se puede, la cita queda igual y la
reintenta la tarea de fichas automáticas.

Reglas de negocio (antes en la vista): vigencia del paciente, clínica del
paciente contra el centro del consultorio, consultorio familiar (P-03),
horario libre (``CitasRepository.create``) y reagendado de una cita
afectada por P-03, todo en una transacción.

La autorización queda en quien llama: permiso y alcance por centro en la
vista de recepción; "solo en tu propia agenda" en el seguimiento del médico.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.catalogos.models.consultorios import Consultorios
from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO, CanalMovimiento, CitaMedica
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.clinica_paciente_service import centro_del_paciente, centro_permitido
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.services.vigencia_service import tiene_vigencia
from apps.recepcion.uses_case.adscripcion_usecase import (
    paciente_por_llave,
    validar_consultorio_familiar,
    vincular_reagenda,
)
from apps.recepcion.uses_case.materializar_fichas_usecase import genera_ficha_automatica, materializar_ficha

logger = logging.getLogger(__name__)


def notas_de_cita_de_seguimiento(visit_folio: str) -> str:
    """Notas con las que la cita de seguimiento apunta a su consulta."""
    return f"Consulta {visit_folio}"


def _validar_clinica_paciente(no_exp: str, pk_num: int, consultorio_id: int) -> None:
    """
    El paciente (empleado o derechohabiente) tiene que pertenecer al centro
    del consultorio. Regla compartida con el portal
    (``services/clinica_paciente_service.py``): sin dato de clínica o centro
    sin asignar no se bloquea.
    """
    centro_paciente = centro_del_paciente(no_exp, pk_num)
    centro_consultorio = (
        Consultorios.objects.filter(id=consultorio_id).values_list("id_center_id", flat=True).first()
    )
    if not centro_permitido(centro_paciente, centro_consultorio):
        raise VisitDomainError(
            "WRONG_CLINIC",
            f"El paciente pertenece a la clínica {centro_paciente} y no puede "
            f"agendar cita en este centro de atención.",
            400,
        )


def agendar_cita(
    *,
    no_exp,
    pk_num,
    medico_id,
    fecha_hora,
    created_by_id,
    operador,
    request,
    id_paciente=None,
    consultorio_id=None,
    duracion_min=20,
    servicio_tipo="medicina_general",
    motivo=None,
    notas=None,
    id_cita_afectada=None,
    excepcion_consultorio_familiar=None,
    canal=CanalMovimiento.RECEPCION,
    reprogramada_de=None,
    seguimiento_de_visita=None,
) -> dict:
    """
    Crea la cita o lanza VisitDomainError. ``operador`` es un Operador o una
    función que lo arma: P-03 solo lo usa para una excepción o un reagendado.
    """
    paciente = paciente_por_llave(id_paciente=id_paciente, no_exp=no_exp, pk_num=pk_num)
    if seguimiento_de_visita is not None:
        # La cita de seguimiento que indicó el médico: mismo paciente, y queda
        # enlazada a su consulta igual que la que agenda el médico.
        if paciente is None or paciente.pk != seguimiento_de_visita.patient_id:
            raise VisitDomainError(
                "SEGUIMIENTO_DE_OTRO_PACIENTE", "El seguimiento es de otro paciente.", 422,
            )
        motivo = MOTIVO_CITA_SEGUIMIENTO
        notas = notas_de_cita_de_seguimiento(seguimiento_de_visita.folio)

    # Sin vigencia no se agenda (la orden de Capital Humano se acepta en el
    # check-in, no acá).
    if not tiene_vigencia(no_exp, pk_num):
        raise VisitDomainError(
            "PATIENT_NO_SERVICE",
            "El paciente no tiene vigencia activa; no se le puede agendar una cita.",
            409,
        )

    if consultorio_id:
        _validar_clinica_paciente(no_exp, pk_num, consultorio_id)

    # P-03 (A1): medicina general en el consultorio familiar.
    validar_consultorio_familiar(
        paciente=paciente,
        consultorio_id=consultorio_id,
        servicio_tipo=servicio_tipo,
        excepcion_motivo=excepcion_consultorio_familiar,
        operador=operador,
        request=request,
        recurso="cita",
    )

    try:
        # P-03: si reagenda una cita afectada, se marca en la misma
        # transacción; si no se puede, la cita nueva no queda creada.
        with transaction.atomic():
            cita = CitasRepository.create(
                no_exp=no_exp,
                pk_num=pk_num,
                medico_id=medico_id,
                consultorio_id=consultorio_id,
                fecha_hora=fecha_hora,
                duracion_min=duracion_min,
                servicio_tipo=servicio_tipo,
                motivo=motivo,
                notas=notas,
                created_by_id=created_by_id,
                canal=canal,
                reprogramada_de=reprogramada_de,
            )
            if id_cita_afectada:
                vincular_reagenda(
                    id_cita_afectada=id_cita_afectada,
                    cita_nueva=CitaMedica.objects.get(pk=cita["id"]),
                    operador=operador() if callable(operador) else operador,
                    request=request,
                )
    except ValueError as exc:
        # Ocupado, ausencia, tope por día, etc.
        raise VisitDomainError("CITA_NOT_AVAILABLE", str(exc), 400) from exc
    _ficha_si_es_hoy(cita["id"])
    return cita


def _ficha_si_es_hoy(cita_id) -> None:
    cita = CitaMedica.objects.get(pk=cita_id)
    if timezone.localtime(cita.fecha_hora).date() != timezone.localdate() or not genera_ficha_automatica(cita):
        return
    try:
        materializar_ficha(cita)
    except VisitDomainError as exc:
        logger.info("La cita %s quedó sin ficha automática: %s", cita.folio, exc.code)
    except Exception:
        # La cita ya quedó agendada: la ficha la reintenta la tarea.
        logger.exception("Error creando la ficha automática de la cita %s", cita.folio)
