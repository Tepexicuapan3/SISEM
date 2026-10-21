from apps.authentication.services.permission_dependencies import (
    get_permission_dependency_closure,
)
from apps.catalogos.models import Permisos


def split_permission_code(code):
    parts = code.split(":")
    if len(parts) < 2:
        return None, None
    return ":".join(parts[:-1]), parts[-1]


def ensure_read_dependencies(permission_ids):
    """Expande los ids pedidos con el cierre transitivo de dependencias.

    Usa get_permission_dependency_closure (explicitas + :read inferido, respetando
    NO_INFERRED_READ_DEPENDENCY). Codigos de dependencia inexistentes o inactivos
    se ignoran; los ids pedidos se conservan siempre.
    """
    requested = set(permission_ids)
    codes = set(
        Permisos.objects.filter(
            id_permiso__in=requested,
            is_active=True,
        ).values_list("codigo", flat=True)
    )

    dependency_codes = set()
    for code in codes:
        dependency_codes.update(get_permission_dependency_closure(code))
    dependency_codes -= codes

    expanded = set(requested)
    if dependency_codes:
        expanded.update(
            Permisos.objects.filter(
                codigo__in=dependency_codes,
                is_active=True,
            ).values_list("id_permiso", flat=True)
        )

    return expanded
