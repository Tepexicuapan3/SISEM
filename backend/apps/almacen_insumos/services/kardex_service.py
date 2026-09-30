"""
kardex_service — ÚNICO punto de escritura para ExistenciaAlmacen y KardexMovimiento.

Nadie más debe modificar esas tablas directamente.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.almacen_insumos.models.kardex import (
    ExistenciaAlmacen,
    KardexMovimiento,
    LoteInsumo,
)
from apps.almacen_insumos.models.catalogos import Almacen, CatInsumo


class InsufficientStockError(Exception):
    """Stock disponible menor a la cantidad solicitada."""


_TIPOS_ENTRADA = frozenset(
    [
        KardexMovimiento.TipoMovimiento.ENTRADA,
        KardexMovimiento.TipoMovimiento.DEVOLUCION,
        KardexMovimiento.TipoMovimiento.AJUSTE_POSITIVO,
    ]
)

_TIPOS_SALIDA = frozenset(
    [
        KardexMovimiento.TipoMovimiento.SALIDA,
        KardexMovimiento.TipoMovimiento.MERMA,
        KardexMovimiento.TipoMovimiento.CONSUMO,
        KardexMovimiento.TipoMovimiento.AJUSTE_NEGATIVO,
    ]
)


def registrar_movimiento(
    *,
    insumo: CatInsumo,
    lote: LoteInsumo | None,
    almacen: Almacen,
    tipo: KardexMovimiento.TipoMovimiento,
    cantidad: Decimal,
    ref_modelo: str,
    ref_id: int,
    created_by_id: int | None = None,
) -> KardexMovimiento:
    """Registra un movimiento en el kardex y actualiza el saldo.

    Requiere cantidad > 0 para todos los tipos.
    Para SALIDA/MERMA/CONSUMO/AJUSTE_NEGATIVO valida stock suficiente.
    Lanza InsufficientStockError si el stock resultaría negativo.
    """
    if cantidad <= Decimal("0"):
        raise ValueError("La cantidad debe ser mayor a cero")

    with transaction.atomic():
        existencia, _ = ExistenciaAlmacen.objects.select_for_update().get_or_create(
            id_insumo=insumo,
            id_lote=lote,
            id_almacen=almacen,
            defaults={"cantidad": Decimal("0")},
        )

        if tipo in _TIPOS_ENTRADA:
            existencia.cantidad += cantidad
        elif tipo in _TIPOS_SALIDA:
            if existencia.cantidad < cantidad:
                raise InsufficientStockError(
                    f"Stock insuficiente para '{insumo.nombre}': "
                    f"disponible={existencia.cantidad}, solicitado={cantidad}"
                )
            existencia.cantidad -= cantidad
        else:
            raise ValueError(f"Tipo de movimiento desconocido: {tipo}")

        existencia.save(update_fields=["cantidad"])

        movimiento = KardexMovimiento.objects.create(
            id_insumo=insumo,
            id_lote=lote,
            id_almacen=almacen,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            saldo_resultante=existencia.cantidad,
            ref_modelo=ref_modelo,
            ref_id=ref_id,
            created_by_id=created_by_id,
        )

    return movimiento


