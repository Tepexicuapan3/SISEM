"""
Servicio de import masivo de médicos por Excel.

Calca el patrón de `apps.administracion.services.user_import_service`
(openpyxl para escribir la plantilla, pandas para leer/validar). NO persiste
nada -- ni preview ni confirm llaman a este módulo para escribir; ver
`apps.medicos.uses_case.import_medicos`, que re-corre `parse_and_validate`
sobre el MISMO archivo en ambos pasos (mecanismo stateless, sin token/cache).

`normalize_legacy_cd` se exporta pública a propósito: la futura migración de
`det_cirugia.cd_medico` debe normalizar con la MISMA función para que el
join contra `CatMedico.legacy_cd_medico` cierre (ver Engram, topic_key
sdd/medicos-legacy-field-bulk-import/design, "Decisión 4").
"""

import io
import re
import unicodedata
from typing import Optional

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.authentication.models import SyUsuario
from apps.medicos.models import CatMedico, ESTATUS_MEDICO, TIPO_MEDICO

HEADERS = [
    "ID del Médico",
    "Usuario (Login del sistema)",
    "Nombre del Médico",
    "Tipo de Médico",
    "Servicio",
    "Estatus del Médico",
    "Observaciones",
]

MAX_ROWS = 5000

DEFAULT_TIPO_MEDICO = "CLINICA"
DEFAULT_ESTATUS_MEDICO = "ACTIVO"

# Sentinelas basura del legado -> None (para que `unique=True` no colisione:
# Postgres/SQLite tratan NULLs como distintos). `E00000`/`H99999` NO estan
# en este set: son claves sintacticamente validas e indistinguibles de
# claves reales -- se confirmo que son claves reales, no basura (ver
# Engram, topic_key sdd/medicos-legacy-field-bulk-import/design).
_SENTINELAS = {
    "", "S/C", "SC", "S\\C", "S / C", "SN", "S/N", "N/A", "NA",
    "-", "--", "NULL", "NONE", "0",
}

# Códigos de error de fila de esta importación (documentales -- el mensaje
# que efectivamente ve el usuario en el preview es texto libre en español,
# ver `parse_and_validate`; estos códigos identifican el escenario para
# spec/tests, ver Engram topic_key sdd/medicos-legacy-field-bulk-import/spec).
# `ROW_INVALID_TIPO_MEDICO` / `ROW_INVALID_ESTATUS` se agregaron para cerrar
# el CRITICAL de verify: un valor NO-vacío que no matchea ningún choice
# (typo) caía al default en silencio, sin marcar error de fila.
ROW_ERROR_CODES = (
    "ROW_USER_NOT_FOUND",
    "ROW_MEDICO_ALREADY_EXISTS",
    "ROW_LEGACY_ALREADY_EXISTS",
    "ROW_LEGACY_DUPLICATE_IN_FILE",
    "ROW_INVALID_TIPO_MEDICO",
    "ROW_INVALID_ESTATUS",
)

# Longitudes de los campos libres de CatMedico -- se truncan defensivamente
# antes de crear (mismo criterio que el truncado a 10 chars de
# `normalize_legacy_cd`) para no dejar un IntegrityError sin manejar a
# mitad de `_create_all` por una celda de Excel demasiado larga.
_NOMBRE_DISPLAY_MAX_LEN = 200
_SERVICIO_MAX_LEN = 100

_SAMPLE_ROWS = (
    ("E00000", "jperez", "Dr. Juan Pérez", "Clínica", "Cardiología", "Activo", ""),
    ("", "mgomez", "", "Hospital", "", "Activo", "Médico sin clave legada (alta nativa de SIRES)"),
)


class ImportFileError(Exception):
    """Error de nivel-archivo (headers, extensión, límite de filas): 400, ninguna fila se evalúa."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def build_template() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Médicos"

    BRAND = "D94300"
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor=BRAND)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    for row_idx, sample_row in enumerate(_SAMPLE_ROWS, start=2):
        for col_idx, value in enumerate(sample_row, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    for col_idx, header in enumerate(HEADERS, start=1):
        max_len = max(len(header), *(len(str(row[col_idx - 1])) for row in _SAMPLE_ROWS))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 4, 12), 40)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def _clean_text(value) -> str:
    text = "" if value is None else str(value)
    if text.strip().lower() == "nan":
        text = ""
    return re.sub(r"\s+", " ", text.strip())


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _truncate(text: str, max_length: int) -> str:
    return text[:max_length] if text else text


def normalize_legacy_cd(value) -> Optional[str]:
    """
    Sentinelas basura del legado ("S/C", "SN", vacío, etc.) -> None, para
    que `unique=True` en `CatMedico.legacy_cd_medico` no colisione entre
    médicos sin clave legada real. Cualquier otro valor se pasa a
    mayúsculas y se trunca defensivamente a 10 chars (max_length del
    campo). Pública -- reusar SIEMPRE esta función para normalizar
    `det_cirugia.cd_medico` en migraciones futuras, o el join no cierra.
    """
    text = _clean_text(value).upper()
    if text in _SENTINELAS:
        return None
    return text[:10] or None


def _build_choice_lookup(choices) -> dict:
    lookup = {}
    for code, label in choices:
        lookup[_strip_accents(code).lower()] = code
        lookup[_strip_accents(label).lower()] = code
    return lookup


_TIPO_MEDICO_LOOKUP = _build_choice_lookup(TIPO_MEDICO)
_ESTATUS_MEDICO_LOOKUP = _build_choice_lookup(ESTATUS_MEDICO)


def _resolve_choice(raw_text: str, lookup: dict, default: str) -> tuple[str, bool]:
    """
    Resuelve un choice de `CatMedico` (Tipo de Médico / Estatus) por label
    o código, insensible a acentos/mayúsculas.

    Devuelve `(valor_resuelto, es_valido)`:
    - Vacío -> `(default, True)`. Comportamiento intencional y documentado
      en la plantilla/dialog: "vacío se interpreta como <default>".
    - No vacío y matchea un choice -> `(codigo, True)`.
    - No vacío y NO matchea ningún choice (typo/valor inventado) ->
      `(default, False)`. El caller (`parse_and_validate`) es responsable
      de agregar `ROW_INVALID_TIPO_MEDICO` / `ROW_INVALID_ESTATUS` a la
      fila cuando `es_valido` es False -- ver `ROW_ERROR_CODES` arriba.
    """
    if not raw_text:
        return default, True
    resolved = lookup.get(_strip_accents(raw_text).lower())
    if resolved is None:
        return default, False
    return resolved, True


def parse_and_validate(file) -> dict:
    """
    Única función de validación, reusada tal cual por preview y por
    confirm -- el confirm NUNCA confía en el resultado que mandó el
    cliente en preview, siempre re-corre esto contra el archivo re-subido
    (mecanismo stateless, ver `import_medicos.py`).

    Devuelve:
        {
            "total_records": int,
            "total_errores": int,
            "rows": [
                {
                    "row": int,             # numero de fila en el Excel (1-based, incluye header)
                    "data": {...},          # datos parseados en camelCase
                    "errors": [str, ...],   # vacio si la fila es valida
                },
                ...
            ],
        }
    """
    df = _read_dataframe(file)
    total_records = len(df)

    raw_rows = []
    for row_idx in range(total_records):
        raw_rows.append(
            {
                "legacyCdRaw": _clean_text(df.iloc[row_idx]["ID del Médico"]),
                "usuario": _clean_text(df.iloc[row_idx]["Usuario (Login del sistema)"]),
                "nombreDisplayRaw": _clean_text(df.iloc[row_idx]["Nombre del Médico"]),
                "tipoMedicoRaw": _clean_text(df.iloc[row_idx]["Tipo de Médico"]),
                "servicioRaw": _clean_text(df.iloc[row_idx]["Servicio"]),
                "estatusRaw": _clean_text(df.iloc[row_idx]["Estatus del Médico"]),
                "observacionesRaw": _clean_text(df.iloc[row_idx]["Observaciones"]),
            }
        )

    legacy_normalized = [normalize_legacy_cd(r["legacyCdRaw"]) for r in raw_rows]
    legacy_seen: dict = {}
    for code in legacy_normalized:
        if code:
            legacy_seen[code] = legacy_seen.get(code, 0) + 1

    usernames = [r["usuario"] for r in raw_rows if r["usuario"]]
    usuarios_by_username = {
        u.usuario: u for u in SyUsuario.objects.filter(usuario__in=usernames)
    }
    existing_medico_usuario_ids = set(
        CatMedico.objects.filter(
            id_usuario_id__in=[u.id_usuario for u in usuarios_by_username.values()]
        ).values_list("id_usuario_id", flat=True)
    )
    existing_legacy_codes = set(
        CatMedico.objects.filter(
            legacy_cd_medico__in=[c for c in legacy_normalized if c]
        ).values_list("legacy_cd_medico", flat=True)
    )

    result_rows = []
    total_errores = 0

    for row_idx, parsed in enumerate(raw_rows):
        errors = []

        usuario_obj = None
        if not parsed["usuario"]:
            errors.append("Usuario (Login del sistema) es obligatorio.")
        else:
            usuario_obj = usuarios_by_username.get(parsed["usuario"])
            if usuario_obj is None:
                errors.append(
                    f"No existe un usuario con nombre de usuario '{parsed['usuario']}'."
                )
            elif usuario_obj.id_usuario in existing_medico_usuario_ids:
                errors.append("Este usuario ya tiene un perfil de médico.")

        legacy_value = legacy_normalized[row_idx]
        if legacy_value:
            if legacy_seen.get(legacy_value, 0) > 1:
                errors.append("ID del Médico duplicado en el archivo.")
            elif legacy_value in existing_legacy_codes:
                errors.append(
                    f"Ya existe un médico con el ID del Médico '{legacy_value}'."
                )

        tipo_medico_value, tipo_medico_valid = _resolve_choice(
            parsed["tipoMedicoRaw"], _TIPO_MEDICO_LOOKUP, DEFAULT_TIPO_MEDICO
        )
        if not tipo_medico_valid:
            errors.append(
                f"Tipo de Médico '{parsed['tipoMedicoRaw']}' no es válido. "
                f"Valores permitidos: {', '.join(code for code, _ in TIPO_MEDICO)}."
            )

        estatus_value, estatus_valid = _resolve_choice(
            parsed["estatusRaw"], _ESTATUS_MEDICO_LOOKUP, DEFAULT_ESTATUS_MEDICO
        )
        if not estatus_valid:
            errors.append(
                f"Estatus del Médico '{parsed['estatusRaw']}' no es válido. "
                f"Valores permitidos: {', '.join(code for code, _ in ESTATUS_MEDICO)}."
            )

        row_data = {
            "legacyCdMedico": legacy_value,
            "usuario": parsed["usuario"],
            "usuarioId": usuario_obj.id_usuario if usuario_obj else None,
            "nombreDisplay": _truncate(parsed["nombreDisplayRaw"], _NOMBRE_DISPLAY_MAX_LEN) or None,
            "tipoMedico": tipo_medico_value,
            "servicio": _truncate(parsed["servicioRaw"], _SERVICIO_MAX_LEN) or None,
            "estatusMedico": estatus_value,
            "observaciones": parsed["observacionesRaw"] or None,
        }

        result_rows.append(
            {
                "row": row_idx + 2,  # +1 header, +1 para 1-based
                "data": row_data,
                "errors": errors,
            }
        )
        if errors:
            total_errores += 1

    return {
        "total_records": total_records,
        "total_errores": total_errores,
        "rows": result_rows,
    }


def _read_dataframe(file) -> pd.DataFrame:
    filename = (getattr(file, "name", "") or "").lower()
    if not filename.endswith((".xlsx", ".xls")):
        raise ImportFileError(
            code="IMPORT_FILE_INVALID",
            message="El archivo debe ser .xlsx o .xls.",
        )

    try:
        df = pd.read_excel(file, dtype=str, engine="openpyxl" if filename.endswith(".xlsx") else None)
    except Exception as exc:
        raise ImportFileError(
            code="IMPORT_FILE_INVALID",
            message="No se pudo leer el archivo. Verifique que sea un Excel válido.",
        ) from exc

    df = df.fillna("")

    actual_headers = [str(c).strip() for c in df.columns.tolist()]
    if actual_headers != HEADERS:
        raise ImportFileError(
            code="IMPORT_HEADERS_MISMATCH",
            message="Las columnas del archivo no coinciden con la plantilla de médicos.",
            details={"expected": HEADERS, "actual": actual_headers},
        )

    if len(df) > MAX_ROWS:
        raise ImportFileError(
            code="IMPORT_TOO_MANY_ROWS",
            message=f"El archivo excede el máximo de {MAX_ROWS} filas.",
        )

    return df
