"""
Equivalencia de familiares del legado (documento "Historia Clinica Unificada",
seccion 8, "Equivalencia de familiares").

En dbclinicas, tp_paciente NO es el PK_NUM de SERMED: es cat_familiar.cd_familiar
(0 = trabajador). Lo dice el propio legado en det_consultoriofam: "TRABAJADOR-0 Y
CD_FAMILIAR CAT_FAMILIAR". Este mapa traduce cd_familiar -> PK_NUM leyendo el
cat_familiar del legado (columnas cd_familiar, no_expf, pk_num).

Un cd_familiar NO se traduce cuando:
  - su pk_num es NULL o 0 (0 es del trabajador): el familiar no tiene PK_NUM;
  - su pk_num esta repetido en otro cd_familiar: no se sabe a quien pertenece.
En esos casos el registro conserva el cd_familiar como llave y el paciente se
identifica solo por CD_FAMILIAR.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

LEGACY_FAMILY_QUERY = "SELECT cd_familiar, no_expf, pk_num FROM cat_familiar"


def _int_or_none(value) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class LegacyFamilyMap:
    # cd_familiar -> no_expf (titular)
    titular_by_cd: dict[int, str] = field(default_factory=dict)
    # cd_familiar -> PK_NUM traducible (sin NULL, sin 0, sin repetidos)
    pk_by_cd: dict[int, int] = field(default_factory=dict)
    # cd_familiar cuyo pk_num esta repetido en otro cd_familiar
    ambiguous_cds: set[int] = field(default_factory=set)
    # titular -> cd_familiar / pk_num de sus familiares
    cds_by_titular: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))
    pks_by_titular: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))

    @classmethod
    def from_rows(cls, rows: Iterable) -> "LegacyFamilyMap":
        """``rows``: dicts (DictCursor) o tuplas (cd_familiar, no_expf, pk_num)."""
        fmap = cls()
        raw_pk: dict[int, int | None] = {}
        for row in rows:
            if isinstance(row, dict):
                cd, titular, pk = row.get("cd_familiar"), row.get("no_expf"), row.get("pk_num")
            else:
                cd, titular, pk = row
            cd = _int_or_none(cd)
            if cd is None:
                continue
            titular = str(titular).strip() if titular is not None else ""
            pk = _int_or_none(pk)
            fmap.titular_by_cd[cd] = titular
            fmap.cds_by_titular[titular].add(cd)
            raw_pk[cd] = pk
            if pk:
                fmap.pks_by_titular[titular].add(pk)

        cds_by_pk: dict[int, list[int]] = defaultdict(list)
        for cd, pk in raw_pk.items():
            if pk:
                cds_by_pk[pk].append(cd)
        for pk, cds in cds_by_pk.items():
            if len(cds) > 1:
                fmap.ambiguous_cds.update(cds)
            else:
                fmap.pk_by_cd[cds[0]] = pk
        return fmap

    @classmethod
    def from_legacy_connection(cls, conn) -> "LegacyFamilyMap":
        """Lee cat_familiar del MySQL legado (solo SELECT)."""
        with conn.cursor() as cursor:
            cursor.execute(LEGACY_FAMILY_QUERY)
            return cls.from_rows(cursor.fetchall())

    def record_key(self, no_exp: str, tp_paciente) -> tuple[int, int | None]:
        """
        Llave con la que se guarda un registro del legado: (pk_num, cd_familiar).
        Titular -> (0, None). Familiar traducible -> (PK_NUM, cd_familiar).
        Familiar sin PK_NUM traducible -> (cd_familiar, cd_familiar): conserva el
        cd_familiar como llave hasta que las tablas apunten a id_paciente.
        """
        tp = _int_or_none(tp_paciente) or 0
        if tp == 0:
            return 0, None
        pk = self.pk_by_cd.get(tp)
        if pk is not None and self.titular_by_cd.get(tp) == str(no_exp).strip():
            return pk, tp
        return tp, tp
