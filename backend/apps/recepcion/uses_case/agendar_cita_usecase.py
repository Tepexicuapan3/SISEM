"""
Agendar una cita: un solo camino para recepción (``POST /citas``) y para el
médico que deja el seguimiento al cerrar la consulta.

Reglas de negocio (antes en la vista): vigencia del paciente, clínica del
paciente contra el centro del consultorio, consultorio familiar (P-03),
horario libre (``CitasRepository.create``) y reagendado de una cita
afectada por P-03, todo en una transacción.

La autorización queda en quien llama: permiso y alcance por centro en la
vista de recepción; "solo en tu propia agenda" en el seguimiento del médico.
"""

from django.db import transaction

from apps.catalogos.models.consultorios import Consultorios
from apps.recepcion.models import CitaMedica
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.clinica_paciente_service import centro_del_paciente, centro_permitido
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.services.vigencia_service import tiene_vigencia
from apps.recepcion.uses_case.adscripcion_usecase import (
    paciente_por_llave,
    validar_consultorio_familiar,
    vincular_reagenda,
)


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
) -> dict:
    """
    Crea la cita o lanza VisitDomainError. ``operador`` es un Operador o una
    función que lo arma: P-03 solo lo usa para una excepción o un reagendado.
    """
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
        paciente=paciente_por_llave(id_paciente=id_paciente, no_exp=no_exp, pk_num=pk_num),
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
    return cita
