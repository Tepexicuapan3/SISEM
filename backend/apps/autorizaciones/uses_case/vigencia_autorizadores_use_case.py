"""Vigencia de los autorizadores: aviso por vencer y vencimiento (F7, job diario).

Decisiones del usuario (2026-10-28):
  - El vencimiento NO cambia el estatus: el estado VENCIDO se calcula y la
    politica ya le niega autorizar. Queda en el historial y se avisa, y se puede
    renovar sin reactivarlo.
  - El aviso por vencer va al autorizador y a quienes pueden renovarlo.
Ambos son uno por fecha de fin (idempotentes): el movimiento guarda la fecha
avisada; si se renueva, la fecha nueva vuelve a generar aviso.
"""
from __future__ import annotations

from datetime import date

from django.db import transaction

from .. import events
from ..domain.vigencia import DIAS_AVISO_PREDETERMINADO
from ..models import Autorizador
from ..repositories.autorizador_repository import AutorizadorRepository as Repo


def _registrar(ids_autorizador, tipo_movimiento, evento) -> int:
    registrados = 0
    for id_autorizador in ids_autorizador:
        with transaction.atomic():
            autorizador = Autorizador.objects.select_for_update().filter(pk=id_autorizador).first()
            fin = autorizador.fecha_fin_vigencia.isoformat() if autorizador else None
            # Re-chequeo con la fila bloqueada: dos corridas a la vez no duplican.
            if autorizador is None or autorizador.movimientos.filter(
                tipo_movimiento=tipo_movimiento, datos_nuevos__fechaFinVigencia=fin,
            ).exists():
                continue
            Repo.registrar_movimiento(
                autorizador, tipo_movimiento, id_usuario_responsable=None,  # proceso automatico
                datos_nuevos={"fechaFinVigencia": fin},
            )
            events.publicar(evento(
                id_autorizador=autorizador.pk, id_usuario=autorizador.usuario_id,
                fecha_fin_vigencia=autorizador.fecha_fin_vigencia,
            ))
            registrados += 1
    return registrados


def avisar_por_vencer(hoy: date, dias_aviso: int = DIAS_AVISO_PREDETERMINADO) -> int:
    return _registrar(Repo.ids_por_vencer(hoy, dias_aviso), "AVISO_POR_VENCER", events.AutorizadorPorVencer)


def registrar_vencidos(hoy: date) -> int:
    return _registrar(Repo.ids_vencidos_sin_registrar(hoy), "VENCIMIENTO", events.AutorizadorVencido)
