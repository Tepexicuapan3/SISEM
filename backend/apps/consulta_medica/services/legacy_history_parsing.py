"""
Parseo del texto libre del modelo anterior de historia clinica. Funciones
PURAS (sin modelos ni base de datos): las usan la migracion de datos
`consulta_medica.0029` y los comandos `migrar_*_legacy`.

Formato del texto acumulado del legado (datos_hisclin.jsp):
    <texto> [dd/mm/aaaa (usuario)] - <texto> [dd/mm/aaaa (usuario)] - ...
Confirmado contra el dump real: 21,895 anotaciones con ese separador en
his_clinica. Lo que no calce con el patron (texto anterior a esa funcion)
queda como UNA anotacion sin fecha ni autor.
"""
import datetime
import re
import unicodedata
from decimal import Decimal

_ANNOTATION_RE = re.compile(r"(.*?)\s*\[(\d{2}/\d{2}/\d{4}) \(([^)]*)\)\]\s*-\s*", re.S)

# Respuestas de "no tiene alergias" que el legado guarda como texto -- NO son
# una alergia y no deben generar una fila de Allergy (el texto original se
# conserva igual como nota historica).
_NEGATIVE_ALLERGY_RE = re.compile(
    r"^(negad[ao]s?|niega|niega alergias?|ninguna?s?|no|nada|n/?a|sin alergias?"
    r"|no refiere|se niega|no conocidas?|desconoce|interrogad[ao]s? y negad[ao]s?"
    r"|no alergias?|no alergic[ao]s?|negativ[ao]s?|-+|\.+)$"
)


def _parse_date(raw):
    try:
        return datetime.datetime.strptime(raw, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def split_annotations(text):
    """Devuelve [(contenido, fecha|None, autor|None), ...] en orden."""
    text = (text or "").strip()
    if not text:
        return []
    annotations = []
    last_end = 0
    for match in _ANNOTATION_RE.finditer(text):
        content = match.group(1).strip()
        if content:
            annotations.append((content, _parse_date(match.group(2)), match.group(3).strip() or None))
        last_end = match.end()
    remainder = text[last_end:].strip()
    if remainder:
        annotations.append((remainder, None, None))
    return annotations


def _normalize(text):
    decomposed = unicodedata.normalize("NFKD", text or "")
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_accents).strip().casefold().rstrip(".")


def is_negative_allergy(text):
    return bool(_NEGATIVE_ALLERGY_RE.match(_normalize(text)))


def split_allergy_items(text):
    """Separa una lista de alergias en texto libre ("penicilina, sulfas;
    mariscos") en elementos, descartando respuestas negativas y vacios."""
    items = []
    # Sin "/" a proposito: partiria nombres como "TMP/SMX".
    for part in re.split(r"[,;\n]+", text or ""):
        item = part.strip(" .-\t")
        if item and not is_negative_allergy(item):
            items.append(item)
    return items


def format_legacy_vitals(values):
    """`values`: dict {etiqueta: valor crudo}. Devuelve un texto legible con
    solo los valores presentes, o None si no hay ninguno."""
    parts = [f"{label}: {str(value).strip()}" for label, value in values.items() if value and str(value).strip()]
    return "; ".join(parts) if parts else None


# Rangos de plausibilidad para los signos vitales del legado (varchar libre).
# Perfil del dump 2026-09-03: miles de "0", "." y ".." de relleno, talla en
# metros ("1.65") y en cm ("165"), TA con "//". Lo que caiga fuera del rango
# queda NULL -- el texto original se conserva aparte, nunca se inventa.
_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
_BLOOD_PRESSURE_RE = re.compile(r"^(\d{2,3})\s*/+\s*(\d{2,3})$")
VITALS_RANGES = {
    "weight_kg": (Decimal("0.5"), Decimal("350")),
    "height_cm": (Decimal("30"), Decimal("250")),
    "heart_rate_bpm": (20, 250),
    "temperature_c": (Decimal("30"), Decimal("45")),
    "respiratory_rate_bpm": (5, 80),
    "blood_pressure_systolic": (50, 300),
    "blood_pressure_diastolic": (20, 200),
}


def _number(raw):
    text = (str(raw) if raw is not None else "").strip().replace(",", ".")
    return Decimal(text) if _NUMBER_RE.match(text) else None


def _in_range(field, value):
    low, high = VITALS_RANGES[field]
    return value if value is not None and low <= value <= high else None


def _integer_in_range(field, raw):
    value = _number(raw)
    if value is None or value != value.to_integral_value():
        return None
    return _in_range(field, int(value))


def parse_legacy_vitals(*, weight=None, height=None, blood_pressure=None, pulse=None,
                        temperature=None, respiration=None):
    """Valores crudos del legado -> dict con los campos numericos de
    `LegacyVitalSigns` (None donde el valor no es plausible). La talla menor
    a 3 se interpreta en metros. El IMC se calcula solo si hay peso y talla."""
    parsed = {
        "weight_kg": _in_range("weight_kg", _number(weight)),
        "heart_rate_bpm": _integer_in_range("heart_rate_bpm", pulse),
        "temperature_c": _in_range("temperature_c", _number(temperature)),
        "respiratory_rate_bpm": _integer_in_range("respiratory_rate_bpm", respiration),
        "blood_pressure_systolic": None,
        "blood_pressure_diastolic": None,
        "bmi": None,
    }
    height_value = _number(height)
    if height_value is not None and height_value < 3:
        height_value *= 100
    parsed["height_cm"] = _in_range("height_cm", height_value)

    match = _BLOOD_PRESSURE_RE.match((str(blood_pressure) if blood_pressure is not None else "").strip())
    if match:
        systolic = _in_range("blood_pressure_systolic", int(match.group(1)))
        diastolic = _in_range("blood_pressure_diastolic", int(match.group(2)))
        if systolic is not None and diastolic is not None and systolic > diastolic:
            parsed["blood_pressure_systolic"], parsed["blood_pressure_diastolic"] = systolic, diastolic

    for field in ("weight_kg", "height_cm", "temperature_c"):
        if parsed[field] is not None:
            parsed[field] = parsed[field].quantize(Decimal("0.1") if field == "temperature_c" else Decimal("0.01"))
    if parsed["weight_kg"] is not None and parsed["height_cm"] is not None:
        meters = parsed["height_cm"] / 100
        parsed["bmi"] = (parsed["weight_kg"] / (meters * meters)).quantize(Decimal("0.01"))
    return parsed
