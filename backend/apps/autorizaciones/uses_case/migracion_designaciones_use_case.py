"""F8: migra las designaciones vigentes de cat_designacion_autorizador al modulo nuevo.

Decisiones (2026-10-28):
  - Tipos: 01 (autorizador medico) -> REC, 03 -> LAB, 04 -> GAB, CN -> CNO.
    02 y 05 no tienen equivalente: se reportan y quedan en la pantalla vieja.
  - Sin fe_fin: vence al año del inicio (29/feb -> 28/feb).
  - GLOBAL sin fe_fin NO se migra: la politica vieja no lo habilita y darle
    vigencia ampliaria permisos.
  - Vencidas o sin alcance activo no se migran.
  - Un autorizador por usuario: sus designaciones se vuelven tipos de un solo
    registro, cuya vigencia va del inicio mas antiguo al fin mas lejano. Si el
    usuario ya esta en el modulo nuevo no se toca (se completa a mano).

El alta pasa por AutorizadorUseCase.crear, asi que aplica las mismas reglas que
la pantalla (cedula, usuario activo, alcance) y deja movimiento ALTA. Cada
usuario corre en su propio savepoint: si uno falla, los demas siguen. Sin
`aplicar` todo se revierte al final y queda solo el reporte.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Callable

from django.db import transaction

from ..models import AutorizadorTipo
from ..repositories.designacion_legada_repository import (
    DesignacionLegada,
    DesignacionLegadaRepository as Legado,
)
from .autorizador_use_case import AutorizadorError, AutorizadorUseCase

Auditoria = Callable[..., None]

TIPO_POR_CLAVE_VIEJA = {"01": "REC", "03": "LAB", "04": "GAB", "CN": "CNO"}
ACCION_AUDITORIA = "AutorizadorMigrado"
# Mismo motivo que da la regla A1 cuando el usuario ya tiene registro.
_YA_REGISTRADO = {"AUTHORIZER_EXISTS": "AUTORIZADOR_YA_REGISTRADO"}


class Estado(str, Enum):
    MIGRADA = "MIGRADA"
    YA_MIGRADA = "YA_MIGRADA"
    OMITIDA = "OMITIDA"


@dataclass
class Resultado:
    id_designacion: int
    id_usuario: int
    clave_vieja: str
    clave_nueva: str | None
    estado: Estado
    motivo: str | None = None
    id_autorizador: int | None = None


@dataclass
class Reporte:
    aplicado: bool
    resultados: list[Resultado] = field(default_factory=list)

    def total(self, estado: Estado) -> int:
        return sum(1 for r in self.resultados if r.estado == estado)


def fin_por_omision(inicio: date) -> date:
    try:
        return inicio.replace(year=inicio.year + 1)
    except ValueError:  # 29 de febrero
        return inicio.replace(year=inicio.year + 1, day=28)


def _motivo_para_omitir(designacion: DesignacionLegada, hoy: date) -> str | None:
    if designacion.clave_tipo not in TIPO_POR_CLAVE_VIEJA:
        return "TIPO_SIN_EQUIVALENTE"
    if not designacion.alcances:
        return "SIN_ALCANCE"
    if designacion.fecha_fin is None and any(a[0] == "GLOBAL" for a in designacion.alcances):
        return "GLOBAL_SIN_FECHA_FIN"
    if (designacion.fecha_fin or fin_por_omision(designacion.fecha_inicio)) < hoy:
        return "VENCIDA"
    return None


def _datos_alta(id_usuario: int, designaciones: list[DesignacionLegada]) -> dict:
    tipos, inicios, fines = [], [], []
    for d in designaciones:
        fin = d.fecha_fin or fin_por_omision(d.fecha_inicio)
        inicios.append(d.fecha_inicio)
        fines.append(fin)
        tipos.append({
            "claveTipo": TIPO_POR_CLAVE_VIEJA[d.clave_tipo],
            "fechaInicioVigencia": d.fecha_inicio,
            "fechaFinVigencia": fin,
            "alcance": {
                "global": any(a[0] == "GLOBAL" for a in d.alcances),
                "centros": [a[1] for a in d.alcances if a[0] == "CENTRO"],
                "tiposCentro": [a[2] for a in d.alcances if a[0] == "TIPO_CENTRO"],
            },
        })
    # Cargo y oficio de la designacion mas reciente.
    reciente = max(designaciones, key=lambda d: (d.fecha_inicio, d.id_designacion))
    return {
        "usuarioId": id_usuario,
        "cargo": reciente.cargo,
        "numeroOficio": reciente.numero_oficio,
        "fechaInicioVigencia": min(inicios),
        "fechaFinVigencia": max(fines),
        "tipos": tipos,
    }


def _migrar_usuario(id_usuario, designaciones, *, auditoria, identificador_peticion):
    """Crea el autorizador y marca el origen de cada tipo. Devuelve el id creado."""
    def auditar(_accion, id_recurso, antes, despues):
        auditoria(ACCION_AUDITORIA, id_recurso, antes, despues)

    with transaction.atomic():
        autorizador = AutorizadorUseCase.crear(
            _datos_alta(id_usuario, designaciones),
            actor_id=None,
            puede_otorgar_global=True,
            auditoria=auditar,
            identificador_peticion=identificador_peticion,
        )
        for d in designaciones:
            AutorizadorTipo.objects.filter(
                autorizador=autorizador,
                tipo_autorizacion__clave=TIPO_POR_CLAVE_VIEJA[d.clave_tipo],
                esta_activo=True,
            ).update(id_designacion_origen=d.id_designacion)
    return autorizador.pk


def migrar_designaciones(*, aplicar: bool, hoy: date, auditoria: Auditoria,
                         identificador_peticion: str | None = None) -> Reporte:
    reporte = Reporte(aplicado=aplicar)
    designaciones = Legado.activas()
    ya_migradas = Legado.ids_ya_migrados(d.id_designacion for d in designaciones)

    por_usuario: dict[int, list[DesignacionLegada]] = defaultdict(list)
    for d in designaciones:
        clave_nueva = TIPO_POR_CLAVE_VIEJA.get(d.clave_tipo)
        if d.id_designacion in ya_migradas:
            reporte.resultados.append(
                Resultado(d.id_designacion, d.id_usuario, d.clave_tipo, clave_nueva, Estado.YA_MIGRADA)
            )
            continue
        motivo = _motivo_para_omitir(d, hoy)
        if motivo:
            reporte.resultados.append(
                Resultado(d.id_designacion, d.id_usuario, d.clave_tipo, clave_nueva, Estado.OMITIDA, motivo)
            )
            continue
        por_usuario[d.id_usuario].append(d)

    with transaction.atomic():
        for id_usuario, candidatas in por_usuario.items():
            try:
                id_autorizador = _migrar_usuario(
                    id_usuario, candidatas, auditoria=auditoria, identificador_peticion=identificador_peticion,
                )
                estado, motivo = Estado.MIGRADA, None
            except AutorizadorError as exc:
                id_autorizador, estado = None, Estado.OMITIDA
                motivo = _YA_REGISTRADO.get(exc.code, exc.code)
            reporte.resultados.extend(
                Resultado(
                    d.id_designacion, id_usuario, d.clave_tipo, TIPO_POR_CLAVE_VIEJA[d.clave_tipo],
                    estado, motivo, id_autorizador,
                )
                for d in candidatas
            )
        if not aplicar:
            transaction.set_rollback(True)

    reporte.resultados.sort(key=lambda r: (r.id_usuario, r.id_designacion))
    return reporte
