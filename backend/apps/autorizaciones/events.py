"""Eventos de dominio internos del modulo de autorizaciones.

Los dominios de origen (recetas, pases, notas) se suscriben para reflejar el
resultado en su propio documento. Se publican DENTRO de la transaccion que
resuelve la solicitud: si un suscriptor falla, se revierte todo y la
solicitud y su documento nunca quedan en estados distintos.

Eventos:
  SolicitudResuelta  (AUTORIZADA, RECHAZADA, VENCIDA o CANCELADA)
  SolicitudCreada    (para notificar; F4)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SolicitudResuelta:
    id_solicitud: int
    uuid_publico: str
    folio: str
    clave_tipo: str
    tipo_origen: str
    id_origen: int
    estatus: str
    id_usuario_resolucion: int | None
    clave_motivo: str | None


@dataclass(frozen=True)
class SolicitudCreada:
    id_solicitud: int
    uuid_publico: str
    folio: str
    ids_autorizador_destinatarios: tuple


@dataclass(frozen=True)
class SolicitudEnviada:
    """Envio manual (o reenvio) a autorizadores elegidos."""

    id_solicitud: int
    ids_autorizador: tuple
    id_usuario_envio: int


_suscriptores: dict[str, list[Callable]] = defaultdict(list)


def suscribir(nombre_evento: str, manejador: Callable) -> None:
    if manejador not in _suscriptores[nombre_evento]:
        _suscriptores[nombre_evento].append(manejador)


def desuscribir(nombre_evento: str, manejador: Callable) -> None:
    if manejador in _suscriptores[nombre_evento]:
        _suscriptores[nombre_evento].remove(manejador)


def publicar(evento) -> None:
    for manejador in list(_suscriptores[type(evento).__name__]):
        manejador(evento)
