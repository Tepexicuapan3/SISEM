"""Contrato publico del modulo de autorizaciones para otros dominios.

Recetas, pases y notas NO importan modelos ni repositorios de este modulo:
solo estas funciones. Leen el estado real en cada llamada, asi que la
vigencia, el estatus y los centros se validan en cada operacion, no al
iniciar sesion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from .domain.politica import ESPECIFICIDAD, Decision, Motivo, evaluar
from .repositories.politica_repository import PoliticaRepository as Repo

__all__ = [
    "Decision",
    "Elegible",
    "Motivo",
    "autorizadores_elegibles",
    "cancelar_por_origen",
    "puede_autorizar",
    "solicitar_autorizacion",
    "tiene_solicitud_pendiente",
]


@dataclass(frozen=True)
class Elegible:
    id_usuario: int
    id_autorizador: int
    id_autorizador_tipo: int
    alcance_aplicado: str


def puede_autorizar(
    id_usuario: int | None,
    clave_tipo: str,
    id_centro: int | None,
    *,
    fecha: date | None = None,
    id_usuario_solicitante: int | None = None,
) -> Decision:
    """¿Puede este usuario autorizar `clave_tipo` (LAB/GAB/REC/CNO) en el centro, hoy?

    `id_usuario_solicitante`: quien origino la solicitud (segregacion de funciones).
    Si autoriza, `numero_cedula` trae la cedula con la que firma.
    """
    if not id_usuario or not clave_tipo or not id_centro:
        return Decision(False, Motivo.NO_ES_AUTORIZADOR)

    decision = evaluar(
        Repo.datos_de_usuario(id_usuario, clave_tipo),
        id_centro=id_centro,
        tipo_centro=Repo.tipo_de_centro(id_centro),
        fecha=fecha or timezone.localdate(),
        es_solicitante=id_usuario_solicitante is not None and id_usuario_solicitante == id_usuario,
    )
    if not decision:
        return decision
    return Decision(
        True,
        id_autorizador=decision.id_autorizador,
        id_autorizador_tipo=decision.id_autorizador_tipo,
        alcance_aplicado=decision.alcance_aplicado,
        numero_cedula=Repo.cedula_con_la_que_firma(id_usuario),
    )


def autorizadores_elegibles(
    clave_tipo: str,
    id_centro: int,
    *,
    fecha: date | None = None,
    excluir_id_usuario: int | None = None,
) -> list[Elegible]:
    """Quienes pueden autorizar `clave_tipo` en el centro hoy (para notificarles).

    Cada elegible pasa exactamente la misma politica que `puede_autorizar`.
    Ordenados del alcance mas especifico al mas general.
    """
    tipo_centro = Repo.tipo_de_centro(id_centro)
    if tipo_centro is None:
        return []
    fecha = fecha or timezone.localdate()

    elegibles = []
    for id_usuario, datos in Repo.candidatos(clave_tipo, id_centro, tipo_centro, fecha):
        if id_usuario == excluir_id_usuario:
            continue
        decision = evaluar(datos, id_centro=id_centro, tipo_centro=tipo_centro, fecha=fecha, es_solicitante=False)
        if decision:
            elegibles.append(Elegible(
                id_usuario=id_usuario,
                id_autorizador=decision.id_autorizador,
                id_autorizador_tipo=decision.id_autorizador_tipo,
                alcance_aplicado=decision.alcance_aplicado,
            ))
    return sorted(elegibles, key=lambda e: (ESPECIFICIDAD[e.alcance_aplicado], e.id_autorizador))


def solicitar_autorizacion(
    *,
    clave_tipo: str,
    id_origen: int,
    id_centro: int,
    id_usuario_solicitante: int,
    items: list[dict],
    motivos: list[str],
    folio_origen: str | None = None,
    resumen_minimo: dict | None = None,
    id_paciente: int | None = None,
):
    """Crea (o devuelve) la solicitud pendiente del documento de origen y la
    envia a los autorizadores elegibles. Llamar dentro de la transaccion del
    dominio origen. Si el documento cambio, la solicitud se recalcula.

    items: [{"tipoItem", "idItemOrigen", "descripcion", "cantidad"?, "motivo"?}]
    resumen_minimo: datos para evaluar SIN nombre ni diagnostico del paciente.
    """
    from .uses_case.solicitud_use_case import SolicitudUseCase

    return SolicitudUseCase.solicitar(
        clave_tipo=clave_tipo,
        id_origen=id_origen,
        id_centro=id_centro,
        id_usuario_solicitante=id_usuario_solicitante,
        items=items,
        motivos=motivos,
        folio_origen=folio_origen,
        resumen_minimo=resumen_minimo,
        id_paciente=id_paciente,
    )


def cancelar_por_origen(tipo_origen: str, id_origen: int, *, id_usuario: int) -> bool:
    """El documento de origen se cancelo: cancela su solicitud pendiente (si hay)."""
    from .uses_case.solicitud_use_case import SolicitudUseCase

    return SolicitudUseCase.cancelar_por_origen(tipo_origen, id_origen, id_usuario=id_usuario)


def tiene_solicitud_pendiente(tipo_origen: str, id_origen: int) -> bool:
    """True si el documento de origen tiene una solicitud PENDIENTE en el motor
    (su decision se toma desde la bandeja de autorizaciones)."""
    from .models import Solicitud

    return Solicitud.objects.filter(
        tipo_origen=tipo_origen, id_origen=id_origen, estatus=Solicitud.Estatus.PENDIENTE,
    ).exists()
