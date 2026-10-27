"""Politica de autorizacion medica: decide si un autorizador puede autorizar un
tipo de solicitud en un centro, en una fecha. Funcion pura (sin base de datos):
el contrato le pasa el estado leido en ese momento.

Orden de las verificaciones (la primera que falla es el motivo):
  1. es autorizador          5. vigencia del autorizador (inclusiva)
  2. el centro existe        6. tipo asignado y su vigencia propia
  3. usuario activo          7. cedula, si el tipo la exige
  4. estatus ACTIVO          8. el alcance cubre el centro
                             9. no autoriza lo que el mismo origino
Si varios alcances cubren el centro, gana el mas especifico (CENTRO > TIPO_CENTRO > GLOBAL).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Motivo(str, Enum):
    NO_ES_AUTORIZADOR = "NO_ES_AUTORIZADOR"
    CENTRO_NO_ENCONTRADO = "CENTRO_NO_ENCONTRADO"
    USUARIO_INACTIVO = "USUARIO_INACTIVO"
    AUTORIZADOR_INACTIVO = "AUTORIZADOR_INACTIVO"
    AUTORIZADOR_SUSPENDIDO = "AUTORIZADOR_SUSPENDIDO"
    VIGENCIA_NO_INICIADA = "VIGENCIA_NO_INICIADA"
    VIGENCIA_VENCIDA = "VIGENCIA_VENCIDA"
    TIPO_NO_ASIGNADO = "TIPO_NO_ASIGNADO"
    TIPO_FUERA_DE_VIGENCIA = "TIPO_FUERA_DE_VIGENCIA"
    CEDULA_REQUERIDA = "CEDULA_REQUERIDA"
    CENTRO_NO_ASIGNADO = "CENTRO_NO_ASIGNADO"
    AUTOAUTORIZACION = "AUTOAUTORIZACION"

    @property
    def mensaje(self) -> str:
        return _MENSAJES[self]


_MENSAJES = {
    Motivo.NO_ES_AUTORIZADOR: "No estás registrado como autorizador médico.",
    Motivo.CENTRO_NO_ENCONTRADO: "No se encontró el centro de atención de la solicitud.",
    Motivo.USUARIO_INACTIVO: "Tu usuario está inactivo en SIRES.",
    Motivo.AUTORIZADOR_INACTIVO: "Tu registro de autorizador está dado de baja.",
    Motivo.AUTORIZADOR_SUSPENDIDO: "Tu registro de autorizador está suspendido.",
    Motivo.VIGENCIA_NO_INICIADA: "Tu vigencia como autorizador todavía no inicia.",
    Motivo.VIGENCIA_VENCIDA: "Tu vigencia como autorizador está vencida.",
    Motivo.TIPO_NO_ASIGNADO: "No tienes asignado este tipo de autorización.",
    Motivo.TIPO_FUERA_DE_VIGENCIA: "Tu permiso para este tipo de autorización no está vigente hoy.",
    Motivo.CEDULA_REQUERIDA: "Este tipo de autorización exige cédula profesional y no tienes una registrada en Usuarios.",
    Motivo.CENTRO_NO_ASIGNADO: "No tienes asignado el centro de atención de esta solicitud.",
    Motivo.AUTOAUTORIZACION: "No puedes autorizar una solicitud que tú mismo originaste.",
}

ESPECIFICIDAD = {"CENTRO": 0, "TIPO_CENTRO": 1, "GLOBAL": 2}


@dataclass(frozen=True)
class DatosTipoAsignado:
    id_autorizador_tipo: int
    requiere_cedula: bool
    fecha_inicio_vigencia: date | None
    fecha_fin_vigencia: date | None
    # ((tipo_alcance, id_centro, tipo_centro), ...) solo los activos
    alcances: tuple


@dataclass(frozen=True)
class DatosAutorizador:
    id_autorizador: int
    estatus: str
    fecha_inicio_vigencia: date
    fecha_fin_vigencia: date
    usuario_activo: bool
    tiene_cedula: bool
    tipo: DatosTipoAsignado | None


@dataclass(frozen=True)
class Decision:
    """Se comporta como bool (`if decision:`)."""

    autorizado: bool
    motivo: Motivo | None = None
    id_autorizador: int | None = None
    id_autorizador_tipo: int | None = None
    alcance_aplicado: str | None = None
    numero_cedula: str | None = None

    def __bool__(self) -> bool:
        return self.autorizado

    @property
    def mensaje(self) -> str:
        return self.motivo.mensaje if self.motivo else ""


def _no(motivo: Motivo, autorizador: DatosAutorizador | None = None) -> Decision:
    return Decision(False, motivo, id_autorizador=autorizador.id_autorizador if autorizador else None)


def _alcance_que_cubre(alcances, id_centro, tipo_centro) -> str | None:
    cubren = [
        tipo_alcance
        for tipo_alcance, centro, tipo in alcances
        if (tipo_alcance == "CENTRO" and centro == id_centro)
        or (tipo_alcance == "TIPO_CENTRO" and tipo == tipo_centro)
        or tipo_alcance == "GLOBAL"
    ]
    return min(cubren, key=ESPECIFICIDAD.__getitem__) if cubren else None


def evaluar(
    autorizador: DatosAutorizador | None,
    *,
    id_centro: int,
    tipo_centro: str | None,
    fecha: date,
    es_solicitante: bool,
) -> Decision:
    if autorizador is None:
        return _no(Motivo.NO_ES_AUTORIZADOR)
    if tipo_centro is None:
        return _no(Motivo.CENTRO_NO_ENCONTRADO, autorizador)
    if not autorizador.usuario_activo:
        return _no(Motivo.USUARIO_INACTIVO, autorizador)
    if autorizador.estatus == "INACTIVO":
        return _no(Motivo.AUTORIZADOR_INACTIVO, autorizador)
    if autorizador.estatus != "ACTIVO":
        return _no(Motivo.AUTORIZADOR_SUSPENDIDO, autorizador)
    if fecha < autorizador.fecha_inicio_vigencia:
        return _no(Motivo.VIGENCIA_NO_INICIADA, autorizador)
    if fecha > autorizador.fecha_fin_vigencia:
        return _no(Motivo.VIGENCIA_VENCIDA, autorizador)

    tipo = autorizador.tipo
    if tipo is None:
        return _no(Motivo.TIPO_NO_ASIGNADO, autorizador)
    if (tipo.fecha_inicio_vigencia and fecha < tipo.fecha_inicio_vigencia) or (
        tipo.fecha_fin_vigencia and fecha > tipo.fecha_fin_vigencia
    ):
        return _no(Motivo.TIPO_FUERA_DE_VIGENCIA, autorizador)
    if tipo.requiere_cedula and not autorizador.tiene_cedula:
        return _no(Motivo.CEDULA_REQUERIDA, autorizador)

    alcance = _alcance_que_cubre(tipo.alcances, id_centro, tipo_centro)
    if alcance is None:
        return _no(Motivo.CENTRO_NO_ASIGNADO, autorizador)
    if es_solicitante:
        return _no(Motivo.AUTOAUTORIZACION, autorizador)

    return Decision(
        True,
        id_autorizador=autorizador.id_autorizador,
        id_autorizador_tipo=tipo.id_autorizador_tipo,
        alcance_aplicado=alcance,
    )
