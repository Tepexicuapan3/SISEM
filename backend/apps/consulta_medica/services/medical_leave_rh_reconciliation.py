"""Reconciliacion de incapacidades contra la tabla replicada de RH (SOLO LECTURA).

Change cancelacion-nota-cascada. `dnt_licencias_medicas` vive en la BD
"expedientes" (replica Oracle -> Postgres hecha por administracion, sin modelo
Django; PK `no_folio` varchar(20)). Una incapacidad cuyo folio aparece ahi se
considera ENVIADA a RH y bloquea la cancelacion (LEAVE_SENT_TO_RH).

Notas:
  - SIRES nunca escribe a Oracle ni a esa tabla: unico acceso = SELECT
    parametrizado.
  - Folio SIRES = "LIC-YYYYmmddHHMMSS-{no_exp}" (>= 19 chars + no_exp) vs
    no_folio varchar(20) de RH: para licencias nacidas en SIRES el cruce no
    deberia coincidir nunca; el chequeo es defensivo.
  - Alias, tabla o servidor ausentes/inalcanzables => NO bloquea (se loguea).
    El estado explicito `rh_status` enviada/verificada SI bloquea siempre
    (se evalua en el caso de uso, no aqui).
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import connections

logger = logging.getLogger(__name__)

RH_ALIAS = "expedientes"
RH_TABLE = "dnt_licencias_medicas"
RH_FOLIO_COLUMN = "no_folio"


def find_folios_in_rh(folios: Iterable[str]) -> set[str]:
    """Subconjunto de `folios` que existe en dnt_licencias_medicas.no_folio.

    Nunca lanza: ante cualquier falla de acceso devuelve set() (no bloquea).
    """
    wanted = sorted({folio for folio in folios if folio})
    if not wanted:
        return set()

    try:
        connection = connections[RH_ALIAS]
        placeholders = ", ".join(["%s"] * len(wanted))
        # Identificadores constantes del modulo (no provienen de entrada del
        # usuario); los valores van parametrizados.
        sql = (
            f"SELECT {RH_FOLIO_COLUMN} FROM {RH_TABLE} "
            f"WHERE {RH_FOLIO_COLUMN} IN ({placeholders})"
        )
        with connection.cursor() as cursor:
            cursor.execute(sql, wanted)
            return {str(row[0]).strip() for row in cursor.fetchall()}
    except Exception as exc:  # noqa: BLE001 - alias/tabla/servidor ausentes no bloquean
        logger.warning(
            "No se pudo consultar %s en la BD '%s' (%s: %s); la reconciliacion de incapacidades no bloquea.",
            RH_TABLE, RH_ALIAS, type(exc).__name__, exc,
        )
        return set()
