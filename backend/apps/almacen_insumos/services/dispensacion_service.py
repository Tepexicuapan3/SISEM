"""
dispensacion_service -- crea el `ConsumoConsulta` + N `ConsumoConsultaDetalle`
que registran, contablemente, la dispensacion de farmacia de una receta.

Ver sdd/dispensacion-farmacia/design, seccion (a) y Data Flow: este modulo
es el paso 5 de la transaccion (`prescription_dispensation_usecase.dispense`),
el UNICO que puede fallar por stock insuficiente.

IMPORTANTE -- este servicio NO captura `InsufficientStockError`. El signal
`on_consumo_detail_saved` (almacen_insumos/signals.py) descuenta el stock via
`kardex_service.registrar_movimiento` al guardarse cada
`ConsumoConsultaDetalle`; si el stock no alcanza, la excepcion debe
propagarse tal cual hasta el use-case de `consulta_medica`, que la atrapa
FUERA del `transaction.atomic()` (capturarla adentro del atomic produce
`TransactionManagementError` -- ver design, gotcha de Django en seccion (a)).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from apps.almacen_insumos.models.catalogos import Almacen
from apps.almacen_insumos.models.kardex import (
    ConsumoConsulta,
    ConsumoConsultaDetalle,
)


@dataclass(frozen=True)
class DispensacionLinea:
    """Una linea a descontar: un item de receta ya resuelto a insumo +
    cantidad calculada (Decimal, con factor_conversion ya aplicado). Se
    identifica el insumo/lote por id (no por instancia) -- ya vienen
    resueltos por `MedicamentoInsumo` en el use-case, no hace falta un
    fetch extra de `CatInsumo` solo para asignar la FK."""

    insumo_id: int
    cantidad: Decimal
    prescription_item_id: int
    lote_id: int | None = None


def registrar_dispensacion(
    *,
    almacen: Almacen,
    lineas: list[DispensacionLinea],
    id_cita: int | None = None,
    paciente: str = "",
    observaciones: str = "",
    created_by_id: int | None = None,
) -> ConsumoConsulta:
    """
    Crea UN `ConsumoConsulta` (cabecera) + un `ConsumoConsultaDetalle` por
    cada linea (el `save()` de cada detalle dispara el signal que descuenta
    stock). `medico` se deja en None a proposito -- ver design seccion (d):
    el prescriptor es un `user_id` de `authentication`, no un
    `medicos.CatMedico`; la trazabilidad real la da `prescription_item`.
    """
    consumo = ConsumoConsulta.objects.create(
        id_almacen=almacen,
        id_cita=id_cita,
        paciente=paciente,
        fch_consumo=timezone.localdate(),
        observaciones=observaciones,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )

    for linea in lineas:
        ConsumoConsultaDetalle.objects.create(
            id_consumo=consumo,
            id_insumo_id=linea.insumo_id,
            id_lote_id=linea.lote_id,
            cantidad=linea.cantidad,
            prescription_item_id=linea.prescription_item_id,
        )

    return consumo
