from datetime import timezone as dt_timezone

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.permission_dependencies import (
    get_permission_direct_dependencies,
)


def _to_utc_iso(value):
    if not value:
        return None
    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def _user_name(user):
    if not user:
        return ""
    profile = getattr(user, "detalle", None)
    if profile and profile.nombre_completo:
        return profile.nombre_completo
    return user.usuario or ""


def _user_ref_by_id(user_id, fallback_system=False):
    if not user_id:
        if fallback_system:
            return {"id": 0, "name": "Sistema"}
        return None

    user = UserRepository.get_by_id(user_id)
    if not user:
        if fallback_system:
            return {"id": 0, "name": "Sistema"}
        return None

    return {"id": user.id_usuario, "name": _user_name(user)}


def serialize_role_list(data, repository):
    items = []
    for role in data["roles"]:
        items.append(
            {
                "id": role.id_rol,
                "name": role.rol,
                "description": role.desc_rol,
                "isActive": bool(role.is_active),
                "isSystem": bool(role.es_sistema),
                "isAdmin": bool(role.is_admin),
                "landingRoute": role.landing_route,
                "permissionsCount": repository.count_role_permissions(role),
                "usersCount": repository.count_role_users(role),
                "createdAt": _to_utc_iso(role.created_at),
                "createdBy": _user_ref_by_id(role.created_by_id, fallback_system=True),
                "updatedAt": _to_utc_iso(role.updated_at),
                "updatedBy": _user_ref_by_id(role.updated_by_id),
            }
        )

    return {
        "items": items,
        "page": data["page"],
        "pageSize": data["page_size"],
        "total": data["total"],
        "totalPages": data["total_pages"],
    }


def serialize_role_detail(data):
    role = data["role"]
    permissions = []
    for relation in data["permissions"]:
        permissions.append(
            {
                "id": relation.id_permiso.id_permiso,
                "code": relation.id_permiso.codigo,
                "description": relation.id_permiso.descripcion,
                "assignedAt": _to_utc_iso(relation.fch_asignacion),
                "assignedBy": _user_ref_by_id(
                    relation.usr_asignacion_id, fallback_system=True
                ),
            }
        )

    return {
        "role": {
            "id": role.id_rol,
            "name": role.rol,
            "description": role.desc_rol,
            "isActive": bool(role.is_active),
            "isSystem": bool(role.es_sistema),
            "isAdmin": bool(role.is_admin),
            "landingRoute": role.landing_route,
            "permissionsCount": data["permissions_count"],
            "usersCount": data["users_count"],
            "createdAt": _to_utc_iso(role.created_at),
            "createdBy": _user_ref_by_id(role.created_by_id, fallback_system=True),
            "updatedAt": _to_utc_iso(role.updated_at),
            "updatedBy": _user_ref_by_id(role.updated_by_id),
        },
        "permissions": permissions,
    }


def serialize_permission_catalog(data):
    items = [
        {
            "id": permission.id_permiso,
            "code": permission.codigo,
            "description": permission.descripcion,
            "isSystem": bool(permission.es_sistema),
            "dependsOn": get_permission_direct_dependencies(permission.codigo),
        }
        for permission in data["permissions"]
    ]
    return {
        "items": items,
        "total": data["total"],
    }
