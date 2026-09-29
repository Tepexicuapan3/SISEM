"""
Clasificacion de codigos CIE-10 sensibles (VIH, salud mental, consumo de
sustancias) -- change `diagnosticos-sensibles`. Pura consulta de catalogo,
SIN evaluar permisos aca (ver `consulta_medica.services.diagnosis_redaction_
service` para el punto donde se cruza con `evaluate_permission_requirement`
-- `catalogos` no debe depender de `authentication`).
"""

from functools import lru_cache

from apps.catalogos.models import SensitiveCieRange


@lru_cache(maxsize=1)
def _active_ranges():
    """Cacheado en proceso: el catalogo es chico y cambia con muy poca
    frecuencia (ajuste de calidad/juridico, no una operacion diaria). Se
    invalida con `invalidate_cache()` -- llamarlo despues de escribir
    `SensitiveCieRange` (admin, script de carga, etc.)."""
    return tuple(
        (r.code_prefix_start, r.code_prefix_end, r.category, r.required_permission)
        for r in SensitiveCieRange.objects.filter(is_active=True).order_by("code_prefix_start")
    )


@lru_cache(maxsize=1)
def _roles_by_range_start():
    """CAT_PERFIL_ACCESO: {code_prefix_start: frozenset(codigos de rol)}."""
    from apps.catalogos.models import SensitiveAccessProfile

    result = {}
    for start, role in SensitiveAccessProfile.objects.filter(
        sensitive_range__is_active=True,
    ).values_list("sensitive_range__code_prefix_start", "role__rol"):
        result.setdefault(start, set()).add((role or "").strip().upper())
    return {start: frozenset(roles) for start, roles in result.items()}


def invalidate_cache():
    _active_ranges.cache_clear()
    _roles_by_range_start.cache_clear()


def allowed_roles_for(code):
    """Roles (CAT_PERFIL_ACCESO) que ven sin redaccion el rango de `code`."""
    if not code:
        return frozenset()
    category_prefix = code.strip().upper()[:3]
    for start, end, _category, _permission in _active_ranges():
        if start <= category_prefix <= end:
            return _roles_by_range_start().get(start, frozenset())
    return frozenset()


def classify_cie(code):
    """
    Devuelve `(category, required_permission)` si `code` cae dentro de
    algun rango sembrado en `SensitiveCieRange`, o `None` si no es sensible.

    Compara solo el PREFIJO DE CATEGORIA (letra + 2 digitos, ej. "B24" de
    "B24.9") contra los limites del rango -- NO el codigo completo. Esto
    importa: una comparacion lexicografica sobre el codigo completo
    rompería con subcodigos decimales (`"B24.9" > "B24"` como string, asi
    que quedaria afuera del rango B20-B24 aunque clinicamente SI es VIH).
    Los bloques CIE-10 siempre se definen por categoria de 3 caracteres
    (ej. el bloque "B20-B24" incluye TODOS los subcodigos B20.0..B24.9),
    por eso comparar solo esos 3 caracteres es correcto y suficiente.

    Si `code` cae en mas de un rango (no deberia pasar con rangos bien
    cargados, pero no se asume), devuelve el primero por orden de
    `code_prefix_start`.
    """
    if not code:
        return None

    category_prefix = code.strip().upper()[:3]
    for start, end, category, required_permission in _active_ranges():
        if start <= category_prefix <= end:
            return category, required_permission
    return None
