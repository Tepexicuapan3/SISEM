"""
Reglas de CURP y sexo del paciente (documento "Historia Clinica Unificada", 5.1).

- La CURP nunca lleva un valor de relleno: lo que no cumple el formato oficial
  (por ejemplo 'SIN CURP', que existe en Oracle) se guarda como NULL.
- La fecha de nacimiento (posiciones 5 a 10) y el sexo (posicion 11) de la CURP
  deben coincidir con los del paciente.
- SERMED usa CD_SEXO F = Femenino y M = Masculino; la CURP y SIRES usan
  H = Hombre y M = Mujer. Nunca copiar CD_SEXO tal cual.
"""

from __future__ import annotations

import re
from datetime import date

# Estructura oficial RENAPO: 4 letras, fecha AAMMDD valida en rango, sexo
# (H/M/X), entidad federativa (incluye NE = nacido en el extranjero), 3
# consonantes internas, homoclave y digito verificador.
CURP_REGEX = re.compile(
    r"^[A-Z][AEIOUX][A-Z]{2}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[HMX]"
    r"(AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)"
    r"[B-DF-HJ-NP-TV-Z]{3}[A-Z\d]\d$"
)

# CD_SEXO de SERMED (Oracle) -> sexo de SIRES / CURP.
_SERMED_SEX = {"M": "H", "F": "M"}


def normalize_curp(raw: str | None) -> str | None:
    """CURP en mayusculas y sin espacios, o None si no cumple el formato oficial."""
    value = (raw or "").strip().upper()
    return value if CURP_REGEX.match(value) else None


def birth_date_from_curp(curp: str) -> date | None:
    """Fecha de nacimiento de la CURP. La posicion 17 indica el siglo:
    digito = nacido antes del 2000, letra = del 2000 en adelante."""
    try:
        year = int(curp[4:6])
        century = 1900 if curp[16].isdigit() else 2000
        return date(century + year, int(curp[6:8]), int(curp[8:10]))
    except (ValueError, IndexError):
        return None


def sex_from_curp(curp: str) -> str:
    """Letra de sexo de la CURP: H, M o X."""
    return curp[10]


def sermed_sex_to_sires(cd_sexo: str | None) -> str | None:
    """CD_SEXO de SERMED (F/M) al sexo de SIRES (M/H). Valor desconocido -> None."""
    return _SERMED_SEX.get((cd_sexo or "").strip().upper())


def curp_mismatches(curp: str, *, birth_date: date | None = None, sex: str | None = None) -> dict[str, str]:
    """Diferencias entre la CURP y los datos del paciente: {campo: mensaje}.
    Un dato del paciente que no se conoce no se compara."""
    errors: dict[str, str] = {}
    curp_date = birth_date_from_curp(curp)
    if birth_date and curp_date and curp_date != birth_date:
        errors["birthDate"] = (
            f"La CURP indica nacimiento el {curp_date:%d/%m/%Y}, "
            f"pero el paciente tiene {birth_date:%d/%m/%Y}."
        )
    if sex and sex_from_curp(curp) != sex:
        errors["sex"] = (
            f"La CURP indica sexo '{sex_from_curp(curp)}', pero el paciente tiene '{sex}'."
        )
    return errors
