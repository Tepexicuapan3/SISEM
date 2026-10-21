"""
Servicio de sincronización Oracle → PostgreSQL.

Replica registros de un expediente concreto comparando llaves primarias
y fechas de actualización entre la BD origen (Oracle) y la BD destino (PostgreSQL/Django).

Equivalente al ``actualizar_tabla`` del módulo Flask original.

Transacción: ``sincronizar_tabla`` ya NO hace commit ni se traga errores de
DELETE/INSERT/UPDATE. Quien llama (``actualizar_expediente``) abre una
transacción por expediente en la conexión ``expedientes``: o se aplican las
seis tablas o no se aplica ninguna.

Bitácora: cada fila insertada, modificada o borrada se devuelve como
``CambioReplica`` (valor anterior y nuevo) para guardarla en
``bitacora_replica_sermed`` antes de confirmar la réplica.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import gc
import hashlib
import logging
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

try:
    import oracledb
except ModuleNotFoundError:  # pragma: no cover - depends on image build
    oracledb = None
from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)


def _require_oracledb() -> Any:
    if oracledb is None:
        raise RuntimeError("oracledb no esta disponible en la imagen del backend")
    return oracledb


# ──────────────────────────────────────────────────────────────
# Helpers de bajo nivel (cursores raw)
# ──────────────────────────────────────────────────────────────

def _dividir_lista(lista: list, tamano: int):
    """Generador que parte una lista en bloques de tamaño ``tamano``."""
    for i in range(0, len(lista), tamano):
        yield lista[i:i + tamano]


def _procesar_blob(fila: tuple[Any, ...], indices_blob: list[int]) -> tuple[Any, ...]:
    """Comprime con zlib los campos LOB de una fila de Oracle."""
    db_driver = _require_oracledb()
    fila_editable: list[Any] = list(fila)
    for i in indices_blob:
        if isinstance(fila_editable[i], db_driver.LOB):
            fila_editable[i] = zlib.compress(fila_editable[i].read())
    return tuple(fila_editable)


def _fetch_llaves_oracle(cursor, pk_str: str, tabla: str, no_exp: str,
                         expediente: str, batch_size: int) -> set:
    cursor.execute(
        f"SELECT {pk_str} FROM {tabla} WHERE {no_exp} = :1", (expediente,)
    )
    llaves: set = set()
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            llaves.add(tuple(row))
    return llaves


def _fetch_llaves_postgres(cursor, pk_str: str, tabla: str, no_exp: str,
                           expediente: str, batch_size: int) -> set:
    cursor.execute(
        f'SELECT {pk_str} FROM "{tabla}" WHERE "{no_exp}" = %s', (expediente,)
    )
    llaves: set = set()
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            llaves.add(tuple(row))
    return llaves


def _fetch_fechas_oracle(cursor, pk_str: str, fec_act: str, tabla: str,
                         no_exp: str, expediente: str, batch_size: int) -> dict:
    cursor.execute(
        f"SELECT {pk_str}, {fec_act} FROM {tabla} WHERE {no_exp} = :1", (expediente,)
    )
    idx = len(pk_str.split(","))
    resultado: dict = {}
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        resultado.update({tuple(row[:idx]): row[idx] for row in rows})
    return resultado


def _fetch_fechas_postgres(cursor, pk_str: str, fec_act: str, tabla: str,
                           no_exp: str, expediente: str, batch_size: int) -> dict:
    cursor.execute(
        f'SELECT {pk_str}, {fec_act} FROM "{tabla}" WHERE "{no_exp}" = %s', (expediente,)
    )
    idx = len(pk_str.split(","))
    resultado: dict = {}
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        resultado.update({tuple(row[:idx]): row[idx] for row in rows})
    return resultado


# ──────────────────────────────────────────────────────────────
# Conexión Oracle
# ──────────────────────────────────────────────────────────────

def obtener_conexion_oracle() -> Any:
    db_driver = _require_oracledb()
    cfg = settings.ORACLE_CONFIG
    try:
        db_driver.init_oracle_client(lib_dir=cfg.get('instant_client_dir', r'C:\oracle\instantclient_11_2'))
    except db_driver.ProgrammingError:
        pass  # Ya fue inicializado anteriormente, ignorar
    dsn = db_driver.makedsn(cfg['host'], cfg['port'], service_name=cfg['service_name'])
    return db_driver.connect(user=cfg['user'], password=cfg['password'], dsn=dsn)


BATCH_SIZE = 155


# ──────────────────────────────────────────────────────────────
# Bitácora de la réplica
# ──────────────────────────────────────────────────────────────

ALTA, MODIFICACION, BAJA = "A", "M", "B"   # mismas letras que cns_bitacora_cambios


@dataclass(frozen=True)
class CambioReplica:
    tabla: str
    llave: str
    accion: str
    anterior: dict | None
    nuevo: dict | None


def _valor_bitacora(valor: Any) -> Any:
    """Valor serializable para la bitácora: los binarios (fotos) van como hash."""
    if isinstance(valor, memoryview):
        valor = valor.tobytes()
    if isinstance(valor, (bytes, bytearray)):
        return {"sha256": hashlib.sha256(valor).hexdigest(), "bytes": len(valor)}
    return valor


def _comparable(valor: Any) -> Any:
    """Oracle entrega DATE como datetime a medianoche y la réplica lo guarda
    como date: eso no es un cambio."""
    valor = _valor_bitacora(valor)
    if isinstance(valor, dt.datetime) and valor.tzinfo is None and valor.time() == dt.time():
        return valor.date()
    return valor


def _clave(valores) -> tuple:
    """Clave normalizada para cruzar filas de Oracle y de Postgres."""
    return tuple(str(v).strip() for v in valores)


def _llave_legible(llaves_primarias: list[str], valores) -> str:
    """"no_exp|40041" o "id_empleado|7|id_clave_foto|2" (estilo de cns_bitacora_cambios)."""
    return "|".join(f"{c}|{str(v).strip()}" for c, v in zip(llaves_primarias, valores))


def _fila_bitacora(fila: dict) -> dict:
    return {columna: _valor_bitacora(valor) for columna, valor in fila.items()}


def _fetch_filas_postgres(cursor, tabla: str, columnas: list[str],
                          llaves_primarias: list[str], claves: list[tuple]) -> dict:
    """Filas completas de la réplica para ``claves`` (antes de modificarlas o borrarlas)."""
    col_str = ", ".join(f'"{c}"' for c in columnas)
    indices = [columnas.index(c) for c in llaves_primarias]
    condicion = "(" + " AND ".join(f'"{c}" = %s' for c in llaves_primarias) + ")"
    filas: dict = {}
    for bloque in _dividir_lista(claves, BATCH_SIZE):
        where = " OR ".join([condicion] * len(bloque))
        cursor.execute(
            f'SELECT {col_str} FROM "{tabla}" WHERE {where}',
            [v for clave in bloque for v in clave],
        )
        for row in cursor.fetchall():
            filas[_clave(row[i] for i in indices)] = dict(zip(columnas, row))
    return filas


# ──────────────────────────────────────────────────────────────
# Candado por expediente
# ──────────────────────────────────────────────────────────────

@contextlib.contextmanager
def candado_expediente(expediente: str):
    """
    Evita que dos actualizaciones del mismo expediente se pisen. Advisory lock
    de sesión en la conexión ``expedientes``: si otro proceso ya lo tiene,
    devuelve False sin esperar. Se libera al salir (y Postgres lo libera solo
    si el proceso muere). Fuera de Postgres (tests) siempre lo da.
    """
    conn = connections['expedientes']
    if conn.vendor != 'postgresql':
        yield True
        return
    clave = f"sires:sync_expediente:{str(expediente).strip()}"
    with conn.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [clave])
        adquirido = bool(cursor.fetchone()[0])
    try:
        yield adquirido
    finally:
        if adquirido:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", [clave])
            except Exception:
                logger.exception("No se pudo liberar el candado del expediente %s", expediente)


# ──────────────────────────────────────────────────────────────
# Función principal de sincronización
# ──────────────────────────────────────────────────────────────

def _comprimir_blobs(rows: list, columnas_orden: list[str], columnas_blob: list[str]) -> list:
    indices_blob = [i for i, c in enumerate(columnas_orden) if c in columnas_blob]
    if not indices_blob:
        return rows
    with ThreadPoolExecutor(max_workers=4) as ex:
        return sum(
            ex.map(
                lambda chunk: [_procesar_blob(f, indices_blob) for f in chunk],
                _dividir_lista(rows, 50),
            ),
            [],
        )


def _select_oracle(tabla: str, columnas_sel: str, llaves_primarias: list[str],
                   fec_actualizacion: str, bloque: list) -> tuple[str, list]:
    """SELECT de la versión más reciente de cada llave del bloque."""
    if len(llaves_primarias) == 1:
        ph_ora = ", ".join(f":{i+1}" for i in range(len(bloque)))
        sql = f"""
            SELECT {columnas_sel} FROM (
                SELECT t.*, ROW_NUMBER() OVER (
                    PARTITION BY t.{llaves_primarias[0]}
                    ORDER BY t.{fec_actualizacion} DESC NULLS LAST
                ) AS rn
                FROM {tabla} t
                WHERE {llaves_primarias[0]} IN ({ph_ora})
            ) sub WHERE rn = 1
        """
        return sql, [p[0] for p in bloque]

    conds = ' OR '.join(
        '(' + ' AND '.join(
            f"t.{c} = :{i * len(llaves_primarias) + j + 1}"
            for j, c in enumerate(llaves_primarias)
        ) + ')'
        for i, _ in enumerate(bloque)
    )
    part = ", ".join(f"t.{c}" for c in llaves_primarias)
    sql = f"""
        SELECT {columnas_sel} FROM (
            SELECT t.*, ROW_NUMBER() OVER (
                PARTITION BY {part}
                ORDER BY t.{fec_actualizacion} DESC NULLS LAST
            ) AS rn
            FROM {tabla} t WHERE {conds}
        ) sub WHERE rn = 1
    """
    return sql, [v for par in bloque for v in par]


def sincronizar_tabla(
    oracle_conn: Any,
    tabla: str,
    llaves_primarias: list[str],
    fec_actualizacion: str,
    no_exp: str,
    expediente: str,
    cambios: list[CambioReplica] | None = None,
) -> dict[str, int]:
    """
    Sincroniza una tabla de un expediente. No confirma ni revierte: corre
    dentro de la transacción de quien llama, y cualquier error de base sube.
    Si se pasa ``cambios``, agrega ahí el antes/después de cada fila.
    """
    logger.info("Sincronizando tabla: %s – expediente: %s", tabla.upper(), expediente)
    conteos = {'insertados': 0, 'eliminados': 0, 'actualizados': 0}
    registrar = cambios is not None

    oracle_cursor = oracle_conn.cursor()
    try:
        pg_conn = connections['expedientes']
        with pg_conn.cursor() as pg_cursor:

            # ── Obtener columnas dinámicamente desde PostgreSQL ──────────────
            pg_cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (tabla,))
            columnas_info = pg_cursor.fetchall()

            if not columnas_info:
                # Antes era un warning silencioso: la tabla "se sincronizaba"
                # sin guardar nada. Ahora el expediente falla completo.
                raise RuntimeError(f"La tabla '{tabla}' no existe en la base expedientes.")

            columnas        = [c[0] for c in columnas_info]
            columnas_blob   = [c[0] for c in columnas_info if c[1].lower() in ('bytea',)]
            columnas_act    = [c for c in columnas if c not in llaves_primarias]
            pk_str          = ", ".join(llaves_primarias)

            # Para PostgreSQL: columnas entre comillas (case-sensitive, minúsculas)
            col_str         = ", ".join(f'"{c}"' for c in columnas)

            # Para Oracle: columnas sin comillas (Oracle las convierte a mayúsculas automáticamente)
            col_str_ora     = ", ".join(columnas)
            col_act_str_ora = ", ".join(columnas_act)

            # ── Obtener llaves de ambas BDs ──────────────────────────────────
            llaves_oracle = _fetch_llaves_oracle(
                oracle_cursor, pk_str, tabla, no_exp, expediente, BATCH_SIZE
            )
            llaves_pg = _fetch_llaves_postgres(
                pg_cursor, pk_str, tabla, no_exp, expediente, BATCH_SIZE
            )

            nuevos     = list(llaves_oracle - llaves_pg)
            eliminados = list(llaves_pg - llaves_oracle)
            logger.info("  ↳ Nuevos: %d | Eliminados: %d", len(nuevos), len(eliminados))

            # ── DELETE ──────────────────────────────────────────────────────
            if eliminados:
                t0 = time.time()
                if registrar:
                    # La fila completa ANTES de borrarla: la réplica no guarda historia.
                    previas = _fetch_filas_postgres(pg_cursor, tabla, columnas, llaves_primarias, eliminados)
                    for llave in eliminados:
                        fila = previas.get(_clave(llave))
                        if fila is not None:
                            cambios.append(CambioReplica(
                                tabla, _llave_legible(llaves_primarias, llave), BAJA,
                                _fila_bitacora(fila), None,
                            ))
                where_pk = " AND ".join(f'"{c}" = %s' for c in llaves_primarias)
                sql_del  = f'DELETE FROM "{tabla}" WHERE {where_pk}'
                for bloque in _dividir_lista(eliminados, BATCH_SIZE):
                    pg_cursor.executemany(sql_del, bloque)
                    conteos['eliminados'] += pg_cursor.rowcount
                logger.info("  ↳ Eliminados en %.2fs", time.time() - t0)

            # ── INSERT ──────────────────────────────────────────────────────
            if nuevos:
                t0 = time.time()
                ph_pg   = ", ".join(["%s"] * len(columnas))
                sql_ins = f'INSERT INTO "{tabla}" ({col_str}) VALUES ({ph_pg})'
                indices_pk = [columnas.index(c) for c in llaves_primarias]

                for bloque in _dividir_lista(nuevos, BATCH_SIZE):
                    sql_sel, vals_sel = _select_oracle(
                        tabla, col_str_ora, llaves_primarias, fec_actualizacion, bloque
                    )
                    oracle_cursor.execute(sql_sel, vals_sel)
                    rows = _comprimir_blobs(oracle_cursor.fetchall(), columnas, columnas_blob)

                    pg_cursor.executemany(sql_ins, rows)
                    conteos['insertados'] += pg_cursor.rowcount
                    if registrar:
                        for row in rows:
                            cambios.append(CambioReplica(
                                tabla,
                                _llave_legible(llaves_primarias, [row[i] for i in indices_pk]),
                                ALTA, None, _fila_bitacora(dict(zip(columnas, row))),
                            ))

                logger.info("  ↳ Insertados en %.2fs", time.time() - t0)

            # ── UPDATE ──────────────────────────────────────────────────────
            fechas_oracle = _fetch_fechas_oracle(
                oracle_cursor, pk_str, fec_actualizacion, tabla, no_exp, expediente, BATCH_SIZE
            )
            fechas_pg = _fetch_fechas_postgres(
                pg_cursor, pk_str, fec_actualizacion, tabla, no_exp, expediente, BATCH_SIZE
            )

            actualizar = [k for k in fechas_pg if fechas_pg.get(k) != fechas_oracle.get(k)]
            logger.info("  ↳ Por actualizar: %d", len(actualizar))

            if actualizar:
                t0 = time.time()
                set_clause   = ", ".join(f'"{c}" = %s' for c in columnas_act)
                where_clause = " AND ".join(f'"{c}" = %s' for c in llaves_primarias)
                sql_upd = f'UPDATE "{tabla}" SET {set_clause} WHERE {where_clause}'
                orden_upd = columnas_act + llaves_primarias
                previas = (
                    _fetch_filas_postgres(pg_cursor, tabla, columnas, llaves_primarias, actualizar)
                    if registrar else {}
                )

                for bloque in _dividir_lista(actualizar, BATCH_SIZE):
                    sql_sel, vals_sel = _select_oracle(
                        tabla, f"{col_act_str_ora}, {pk_str}", llaves_primarias,
                        fec_actualizacion, bloque,
                    )
                    oracle_cursor.execute(sql_sel, vals_sel)
                    rows = _comprimir_blobs(oracle_cursor.fetchall(), orden_upd, columnas_blob)

                    pg_cursor.executemany(sql_upd, rows)
                    conteos['actualizados'] += pg_cursor.rowcount
                    if registrar:
                        for row in rows:
                            nueva = dict(zip(orden_upd, row))
                            llave = [nueva[c] for c in llaves_primarias]
                            previa = previas.get(_clave(llave), {})
                            cambiadas = [
                                c for c in columnas_act
                                if _comparable(previa.get(c)) != _comparable(nueva.get(c))
                            ]
                            if cambiadas:
                                cambios.append(CambioReplica(
                                    tabla, _llave_legible(llaves_primarias, llave), MODIFICACION,
                                    {c: _valor_bitacora(previa.get(c)) for c in cambiadas},
                                    {c: _valor_bitacora(nueva.get(c)) for c in cambiadas},
                                ))

                logger.info("  ↳ Actualizados en %.2fs", time.time() - t0)

        return conteos
    finally:
        oracle_cursor.close()
        gc.collect()
