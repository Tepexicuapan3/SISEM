"""
Lectura de la replica de SERMED (cat_empleados / cat_familiar en la conexion
"expedientes"). SOLO LECTURA. La sincronizacion recibe esta fuente como
parametro: en los tests se reemplaza por datos en memoria, sin tocar Oracle
ni la replica.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class SermedEmployee:
    no_exp: str
    paternal_surname: str | None
    maternal_surname: str | None
    first_name: str | None
    birth_date: date | None
    curp: str | None          # tal cual Oracle (puede ser 'SIN CURP')
    sex_code: str | None      # CD_SEXO de SERMED: F = Femenino, M = Masculino
    valid_until: date | None
    leave_date: date | None
    leave_code: str | None
    clinic_code: str | None


@dataclass(frozen=True)
class SermedFamilyMember:
    pk_num: int
    holder_no_exp: str
    paternal_surname: str | None
    maternal_surname: str | None
    first_name: str | None
    birth_date: date | None
    relationship_code: str | None
    beneficiary_type: str | None
    valid_until: date | None
    clinic_code: str | None
    sex_code: str | None = None   # CD_SEXO de SERMED: M = Masculino, F = Femenino


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ReplicaSermedSource:
    """Lee la replica con los modelos de administracion (enrutados a 'expedientes')."""

    def employees(self, no_exps: Iterable[str]) -> dict[str, SermedEmployee]:
        from apps.administracion.models import CatEmpleado

        result = {}
        for row in CatEmpleado.objects.filter(no_exp__in=list(no_exps)):
            no_exp = _text(row.no_exp)
            result[no_exp] = SermedEmployee(
                no_exp=no_exp,
                paternal_surname=_text(row.ds_paterno),
                maternal_surname=_text(row.ds_materno),
                first_name=_text(row.ds_nombre),
                birth_date=row.fe_nac,
                curp=row.curp,
                sex_code=_text(row.cd_sexo),
                valid_until=row.fec_vig,
                leave_date=row.fec_baja,
                leave_code=_text(row.cve_baja),
                clinic_code=_text(row.cd_clinica),
            )
        return result

    def family_members(self, pk_nums: Iterable[int]) -> dict[int, SermedFamilyMember]:
        from apps.administracion.models import CatFamiliar

        result = {}
        for row in CatFamiliar.objects.filter(pk_num__in=list(pk_nums)):
            result[row.pk_num] = SermedFamilyMember(
                pk_num=row.pk_num,
                holder_no_exp=_text(row.no_expf),
                paternal_surname=_text(row.ds_paterno),
                maternal_surname=_text(row.ds_materno),
                first_name=_text(row.ds_nombre),
                birth_date=row.fe_nac,
                relationship_code=_text(row.cd_parentesco),
                beneficiary_type=_text(row.tp_der),
                valid_until=row.fec_vig,
                clinic_code=_text(row.cd_clinica),
                sex_code=_text(row.cd_sexo),
            )
        return result
