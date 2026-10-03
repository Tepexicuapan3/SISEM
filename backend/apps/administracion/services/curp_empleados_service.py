"""
Llenado inicial de CURP y sexo en la replica cat_empleados (historia clinica unificada, 5.1).

Hace falta una sola vez despues de aplicar storage/expedientes-ddl/003: el sync
(sync_service.sincronizar_tabla) solo actualiza una fila cuando cambia su
fec_ult_actualizacion, asi que los empleados ya replicados se quedarian con curp NULL.

Oracle es SOLO LECTURA: aqui unicamente se hace SELECT. Los valores se copian tal cual
vienen de Oracle (incluido 'SIN CURP' y CD_SEXO F/M), igual que el sync. La limpieza y el
mapeo del sexo se hacen al copiar a cns_paciente, no en la replica.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import connections, transaction

# Misma regla que sync_service: si Oracle tiene filas repetidas por NO_EXP,
# gana la de fec_ult_actualizacion mas reciente.
_ORACLE_QUERY = """
    SELECT no_exp, curp, cd_sexo FROM (
        SELECT t.no_exp, t.curp, t.cd_sexo, ROW_NUMBER() OVER (
            PARTITION BY t.no_exp
            ORDER BY t.fec_ult_actualizacion DESC NULLS LAST
        ) AS rn
        FROM cat_empleados t
    ) sub WHERE rn = 1
"""

BATCH_SIZE = 500


def _no_exp_texto(valor: Any) -> str | None:
    """NO_EXP es NUMBER en Oracle y varchar en la replica: 123 / 123.0 / Decimal('123') -> '123'."""
    if valor is None:
        return None
    if isinstance(valor, (int, Decimal)) or (isinstance(valor, float) and valor.is_integer()):
        return str(int(valor))
    return str(valor).strip()


def llenar_curp_empleados(
    oracle_conn: Any,
    *,
    alias: str = "expedientes",
    dry_run: bool = False,
    batch_size: int = BATCH_SIZE,
) -> dict[str, int]:
    """
    Copia CURP y CD_SEXO de Oracle a la replica ``cat_empleados`` de ``alias``.
    Solo actualiza filas cuyo valor difiere, asi que correrlo dos veces no cambia nada.
    Nunca inserta: los empleados que faltan en la replica los trae el sync.
    """
    conteos = {"leidos": 0, "actualizados": 0, "sin_cambio": 0, "no_en_replica": 0}
    oracle_cursor = oracle_conn.cursor()
    try:
        oracle_cursor.execute(_ORACLE_QUERY)
        while True:
            filas = oracle_cursor.fetchmany(batch_size)
            if not filas:
                break
            conteos["leidos"] += len(filas)
            _procesar_lote(filas, alias=alias, dry_run=dry_run, conteos=conteos)
    finally:
        oracle_cursor.close()
    return conteos


def _procesar_lote(filas, *, alias: str, dry_run: bool, conteos: dict[str, int]) -> None:
    desde_oracle: dict[str, tuple[Any, Any]] = {}
    for no_exp, curp, cd_sexo in filas:
        clave = _no_exp_texto(no_exp)
        if clave:
            desde_oracle[clave] = (curp, cd_sexo)

    if not desde_oracle:
        return

    with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
        placeholders = ", ".join(["%s"] * len(desde_oracle))
        cursor.execute(
            f"SELECT no_exp, curp, cd_sexo FROM cat_empleados WHERE no_exp IN ({placeholders})",
            list(desde_oracle),
        )
        en_replica = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        cambios = []
        for no_exp, valores in desde_oracle.items():
            if no_exp not in en_replica:
                conteos["no_en_replica"] += 1
            elif en_replica[no_exp] == valores:
                conteos["sin_cambio"] += 1
            else:
                cambios.append((valores[0], valores[1], no_exp))

        conteos["actualizados"] += len(cambios)
        if cambios and not dry_run:
            cursor.executemany(
                "UPDATE cat_empleados SET curp = %s, cd_sexo = %s WHERE no_exp = %s",
                cambios,
            )
