import uuid
import re
from datetime import datetime, time, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.models import (
    AuditoriaEvento,
    RelRolPermiso,
    RelUsuarioOverride,
    RelUsuarioRol,
)
from django.db import connections
from apps.authentication.models import DetUsuario, DetUsuarioCedula, SyUsuario
from apps.personal.models import (
    DetUsuarioAdministrativo,
    DetUsuarioEnfermeria,
    DetUsuarioMedico,
)
from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.auth_revision import (
    touch_user_auth_revision,
    touch_users_auth_revision,
)
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.email_service import send_notification_email_batch
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.response_service import (
    error_response,
    get_client_ip,
    get_request_id,
)
from apps.authentication.services.session_service import authenticate_request
from apps.catalogos.models import CatAreaClinica, CatCentroAtencion, Permisos, Roles
from apps.administracion.use_cases.rbac_write import (
    AssignUserRolesUseCase,
    SetUserPrimaryRoleUseCase,
    RevokeUserRoleUseCase,
    UpsertUserOverrideUseCase,
    RemoveUserOverrideUseCase,
    RbacWriteError,
)
from apps.administracion.services.rbac_feature_flags import is_rbac_read_s1_enabled
from apps.administracion.use_cases.users.create_user import (
    CedulaInput,
    CreateUserData,
    CreateUserUseCase,
)
from apps.administracion.use_cases.users.password_utils import (
    generate_temporary_password,
)
from django.contrib.auth.hashers import make_password


ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$"
)


def _request_id(request):
    return get_request_id(request) or str(uuid.uuid4())


def _is_rbac_read_s1_enabled():
    return is_rbac_read_s1_enabled()


def _is_rbac_role_mutation_s2_enabled():
    return getattr(settings, "RBAC_ROLE_MUTATION_S2_ENABLED", False)


def _is_rbac_role_permission_s3_enabled():
    return getattr(settings, "RBAC_ROLE_PERMISSION_S3_ENABLED", False)


def _to_utc_iso(value):
    if not value:
        return None
    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_expires_at_end_of_day(raw_value):
    if not raw_value:
        return None

    normalized = str(raw_value).strip()
    if not normalized:
        return None

    if "T" in normalized:
        if not ISO_DATETIME_RE.fullmatch(normalized):
            return "invalid"
        hour_value = int(normalized.split("T", maxsplit=1)[1][:2])
        if hour_value > 23:
            return "invalid"
    elif not ISO_DATE_RE.fullmatch(normalized):
        return "invalid"

    tz = timezone.get_current_timezone()
    try:
        parsed_datetime = parse_datetime(normalized)
    except (TypeError, ValueError, OverflowError):
        return "invalid"

    try:
        if parsed_datetime:
            base = parsed_datetime
        else:
            parsed_date = parse_date(normalized)
            if not parsed_date:
                return "invalid"
            base = datetime.combine(parsed_date, time.min)
    except (TypeError, ValueError, OverflowError):
        return "invalid"

    if base.year >= 9999:
        return "invalid"

    try:
        if timezone.is_naive(base):
            base = timezone.make_aware(base, tz)

        localized = timezone.localtime(base, tz)
        end_of_day = localized.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        end_of_day.astimezone(dt_timezone.utc)
        return end_of_day
    except (TypeError, ValueError, OverflowError):
        return "invalid"


def _apply_user_search_filter(queryset, search, *, path_prefix="", include_correo=True):
    # Busqueda multi-palabra: cada palabra del texto buscado debe aparecer
    # en usuario, correo (opcional) o nombre_completo (en cualquiera de los
    # tres, no necesariamente en el mismo campo). Permite buscar
    # "jgarcia juan" y encontrar al usuario jgarcia01 llamado Juan sin
    # concatenar ni guardar nada nuevo -- se resuelve con los campos
    # existentes en cada consulta.
    #
    # `path_prefix` permite reusar este filtro desde modelos que llegan a
    # SyUsuario/DetUsuario por relacion (ej. "id_usuario__" desde CatMedico).
    if not search:
        return queryset

    for token in search.split():
        query = Q(**{f"{path_prefix}usuario__icontains": token}) | Q(
            **{f"{path_prefix}detalle__nombre_completo__icontains": token}
        )
        if include_correo:
            query |= Q(**{f"{path_prefix}correo__icontains": token})
        queryset = queryset.filter(query)

    return queryset


def _parse_bool(raw_value):
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    return "invalid"


def _parse_pagination(request):
    raw_page = request.query_params.get("page", "1")
    raw_page_size = request.query_params.get("pageSize", "20")

    try:
        page = int(raw_page)
        page_size = int(raw_page_size)
    except (TypeError, ValueError):
        return (
            None,
            None,
            error_response(
                "INVALID_FORMAT",
                "Parametros de paginacion invalidos",
                status.HTTP_400_BAD_REQUEST,
                details={
                    "page": ["Debe ser un entero"],
                    "pageSize": ["Debe ser un entero"],
                },
                request_id=_request_id(request),
            ),
        )

    if page < 1 or page_size < 1 or page_size > 100:
        return (
            None,
            None,
            error_response(
                "VALIDATION_ERROR",
                "Parametros de paginacion fuera de rango",
                status.HTTP_400_BAD_REQUEST,
                details={
                    "page": ["Debe ser mayor o igual a 1"],
                    "pageSize": ["Debe estar entre 1 y 100"],
                },
                request_id=_request_id(request),
            ),
        )

    return page, page_size, None


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


def _clinic_ref(detalle):
    if not detalle or not detalle.id_centro_atencion:
        return None
    center = detalle.id_centro_atencion
    return {"id": center.id, "name": center.name}


def _serialize_permission(permission):
    return {
        "id": permission.id_permiso,
        "code": permission.codigo,
        "description": permission.descripcion,
        "isSystem": bool(permission.es_sistema),
    }


def _role_permissions(role):
    relations = (
        RelRolPermiso.objects.select_related("id_permiso", "usr_asignacion")
        .filter(id_rol=role, fch_baja__isnull=True, id_permiso__is_active=True)
        .order_by("id_permiso__codigo")
    )
    items = []
    for relation in relations:
        items.append(
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
    return items


def _role_counts(role):
    permissions_count = RelRolPermiso.objects.filter(
        id_rol=role,
        fch_baja__isnull=True,
        id_permiso__is_active=True,
    ).count()
    users_count = RelUsuarioRol.objects.filter(
        id_rol=role,
        fch_baja__isnull=True,
        id_usuario__est_activo=True,
    ).count()
    return permissions_count, users_count


def _serialize_role(role):
    permissions_count, users_count = _role_counts(role)
    return {
        "id": role.id_rol,
        "name": role.rol,
        "description": role.desc_rol,
        "isActive": bool(role.is_active),
        "isSystem": bool(role.es_sistema),
        "isAdmin": bool(role.is_admin),
        "landingRoute": role.landing_route,
        "permissionsCount": permissions_count,
        "usersCount": users_count,
        "createdAt": _to_utc_iso(role.created_at),
        "createdBy": _user_ref_by_id(role.created_by_id, fallback_system=True),
        "updatedAt": _to_utc_iso(role.updated_at),
        "updatedBy": _user_ref_by_id(role.updated_by_id),
    }


def _active_user_role_relations(user):
    # Usado en vistas donde el usuario ya viene sin prefetch (ej. detalle de roles).
    return (
        RelUsuarioRol.objects.select_related("id_rol", "usr_asignacion")
        .filter(id_usuario=user, fch_baja__isnull=True, id_rol__is_active=True)
        .order_by("id_usuario_rol")
    )


# Prefetch reutilizable: resuelve el N+1 de roles en listados y exports.
_ROLES_PREFETCH = Prefetch(
    "relusuariorol_set",
    queryset=RelUsuarioRol.objects.select_related("id_rol")
    .filter(fch_baja__isnull=True, id_rol__is_active=True)
    .order_by("id_usuario_rol"),
    to_attr="active_roles_cache",
)


def _get_active_roles(user):
    """Devuelve roles activos usando caché del prefetch si existe, o query directa."""
    cached = getattr(user, "active_roles_cache", None)
    if cached is not None:
        return cached
    return list(_active_user_role_relations(user))


def _active_user_ids_for_role(role):
    return list(
        RelUsuarioRol.objects.filter(id_rol=role, fch_baja__isnull=True)
        .values_list("id_usuario_id", flat=True)
        .distinct()
    )


def _serialize_user_roles(user):
    roles = []
    for relation in _active_user_role_relations(user):
        role = relation.id_rol
        roles.append(
            {
                "id": role.id_rol,
                "name": role.rol,
                "description": role.desc_rol,
                "isPrimary": bool(relation.is_primary),
                "assignedAt": _to_utc_iso(relation.fch_asignacion),
                "assignedBy": _user_ref_by_id(
                    relation.usr_asignacion_id, fallback_system=True
                ),
            }
        )
    return roles


def _serialize_user_overrides(user):
    now = timezone.now()
    overrides = (
        RelUsuarioOverride.objects.select_related("id_permiso", "usr_asignacion")
        .filter(id_usuario=user, fch_baja__isnull=True)
        .order_by("id_override")
    )
    items = []
    for override in overrides:
        is_expired = bool(override.fch_expira and override.fch_expira <= now)
        items.append(
            {
                "id": override.id_override,
                "permissionCode": override.id_permiso.codigo,
                "permissionDescription": override.id_permiso.descripcion,
                "effect": override.efecto,
                "expiresAt": _to_utc_iso(override.fch_expira),
                "isExpired": is_expired,
                "assignedAt": _to_utc_iso(override.fch_asignacion),
                "assignedBy": _user_ref_by_id(
                    override.usr_asignacion_id, fallback_system=True
                ),
            }
        )
    return items


def _serialize_user_list_item(user):
    detail = getattr(user, "detalle", None)
    roles = _get_active_roles(user)
    primary = next((relation for relation in roles if relation.is_primary), None)
    if not primary:
        primary = roles[0] if roles else None

    full_name = ""
    if detail and detail.nombre_completo:
        full_name = detail.nombre_completo

    area = getattr(detail, "id_area_clinica", None) if detail else None
    escolaridad = getattr(detail, "id_escolaridad", None) if detail else None
    escuela = getattr(detail, "id_escuela", None) if detail else None
    tipo_personal = getattr(detail, "id_tipo_personal", None) if detail else None
    cedulas = list(user.cedulas.all()) if hasattr(user, "cedulas") else []

    return {
        "id": user.id_usuario,
        "username": user.usuario,
        "fullname": full_name,
        "fullName": full_name,
        "email": user.correo,
        "clinic": _clinic_ref(detail),
        "areaClinica": {"id": area.id, "name": area.name} if area else None,
        "cdLaboral": detail.cd_laboral if detail else None,
        "telefono": detail.telefono if detail else None,
        "sexo": detail.sexo if detail else None,
        "fechaNac": str(detail.fecha_nac) if detail and detail.fecha_nac else None,
        "escolaridad": {"id": escolaridad.id, "name": escolaridad.name, "isActive": escolaridad.is_active} if escolaridad else None,
        "escuela": {"id": escuela.id, "name": escuela.name, "code": escuela.code, "isActive": escuela.is_active} if escuela else None,
        "tipoPersonal": {"id": tipo_personal.id, "name": tipo_personal.name, "isActive": tipo_personal.is_active} if tipo_personal else None,
        "cedulas": [_serialize_cedula(c) for c in cedulas],
        "primaryRole": primary.id_rol.rol if primary else "",
        "isActive": bool(user.est_activo),
        "termsAccepted": bool(user.terminos_acept),
        "mustChangePassword": bool(user.cambiar_clave),
    }


def _serialize_cedula(cedula):
    return {
        "id": cedula.id,
        "numero": cedula.numero,
        "tipo": cedula.tipo,
        "esPrincipal": cedula.es_principal,
        "orden": cedula.orden,
    }


def _serialize_perfil_medico(user):
    perfil = getattr(user, "perfil_medico", None)
    if not perfil:
        return None
    especialidad = perfil.id_especialidad
    return {
        "cedulaProfesional": perfil.cedula_profesional,
        "cedulaEspecialidad": perfil.cedula_especialidad,
        "especialidad": {"id": especialidad.id, "name": especialidad.name} if especialidad else None,
        "tipoAdscripcion": perfil.tipo_adscripcion,
    }


def _serialize_perfil_enfermeria(user):
    perfil = getattr(user, "perfil_enfermeria", None)
    if not perfil:
        return None
    area = perfil.id_area_clinica
    return {
        "cedulaEnfermeria": perfil.cedula_enfermeria,
        "nivel": perfil.nivel,
        "areaClinica": {"id": area.id, "name": area.name} if area else None,
    }


def _serialize_perfil_administrativo(user):
    perfil = getattr(user, "perfil_administrativo", None)
    if not perfil:
        return None
    return {
        "puesto": perfil.puesto,
        "areaAdministrativa": perfil.area_administrativa,
    }


def _apply_perfil_medico(user, data, actor):
    if data is None:
        DetUsuarioMedico.objects.filter(id_usuario=user).delete()
        return None

    perfil, _ = DetUsuarioMedico.objects.get_or_create(
        id_usuario=user, defaults={"created_by_id": actor.id_usuario}
    )

    if "cedulaProfesional" in data:
        perfil.cedula_profesional = data.get("cedulaProfesional") or None
    if "cedulaEspecialidad" in data:
        perfil.cedula_especialidad = data.get("cedulaEspecialidad") or None
    if "idEspecialidad" in data:
        especialidad_id = data.get("idEspecialidad")
        if especialidad_id is None:
            perfil.id_especialidad = None
        else:
            from apps.catalogos.models import Especialidades
            especialidad = Especialidades.objects.filter(id=especialidad_id).first()
            if not especialidad:
                return ("ESPECIALIDAD_NOT_FOUND", "Especialidad no encontrada")
            perfil.id_especialidad = especialidad
    if "tipoAdscripcion" in data:
        tipo = data.get("tipoAdscripcion") or None
        valid_choices = dict(DetUsuarioMedico._meta.get_field("tipo_adscripcion").choices)
        if tipo is not None and tipo not in valid_choices:
            return (
                "VALIDATION_ERROR",
                f"tipoAdscripcion debe ser uno de: {', '.join(valid_choices)}",
            )
        perfil.tipo_adscripcion = tipo

    perfil.updated_at = timezone.now()
    perfil.updated_by_id = actor.id_usuario
    perfil.save()
    return None


def _apply_perfil_enfermeria(user, data, actor):
    if data is None:
        DetUsuarioEnfermeria.objects.filter(id_usuario=user).delete()
        return None

    perfil, _ = DetUsuarioEnfermeria.objects.get_or_create(
        id_usuario=user, defaults={"created_by_id": actor.id_usuario}
    )

    if "cedulaEnfermeria" in data:
        perfil.cedula_enfermeria = data.get("cedulaEnfermeria") or None
    if "nivel" in data:
        nivel = data.get("nivel") or None
        valid_choices = dict(DetUsuarioEnfermeria._meta.get_field("nivel").choices)
        if nivel is not None and nivel not in valid_choices:
            return (
                "VALIDATION_ERROR",
                f"nivel debe ser uno de: {', '.join(valid_choices)}",
            )
        perfil.nivel = nivel
    if "idAreaClinica" in data:
        area_id = data.get("idAreaClinica")
        if area_id is None:
            perfil.id_area_clinica = None
        else:
            area = CatAreaClinica.objects.filter(id=area_id, is_active=True).first()
            if not area:
                return ("AREA_CLINICA_NOT_FOUND", "Área clínica no encontrada")
            perfil.id_area_clinica = area

    perfil.updated_at = timezone.now()
    perfil.updated_by_id = actor.id_usuario
    perfil.save()
    return None


def _apply_perfil_administrativo(user, data, actor):
    if data is None:
        DetUsuarioAdministrativo.objects.filter(id_usuario=user).delete()
        return None

    perfil, _ = DetUsuarioAdministrativo.objects.get_or_create(
        id_usuario=user, defaults={"created_by_id": actor.id_usuario}
    )

    if "puesto" in data:
        perfil.puesto = data.get("puesto") or None
    if "areaAdministrativa" in data:
        perfil.area_administrativa = data.get("areaAdministrativa") or None

    perfil.updated_at = timezone.now()
    perfil.updated_by_id = actor.id_usuario
    perfil.save()
    return None


def _serialize_user_detail(user):
    detail = getattr(user, "detalle", None)
    # base ya serializa cedulas y roles usando el prefetch cache.
    base = _serialize_user_list_item(user)

    area = getattr(detail, "id_area_clinica", None) if detail else None
    escolaridad = getattr(detail, "id_escolaridad", None) if detail else None
    escuela = getattr(detail, "id_escuela", None) if detail else None

    return {
        **base,
        "perfilMedico": _serialize_perfil_medico(user),
        "perfilEnfermeria": _serialize_perfil_enfermeria(user),
        "perfilAdministrativo": _serialize_perfil_administrativo(user),
        "firstName": detail.nombre if detail else "",
        "paternalName": detail.paterno if detail else "",
        "maternalName": detail.materno if detail and detail.materno else "",
        "noExp": detail.no_exp if detail else None,
        "telefono": detail.telefono if detail else None,
        "sexo": detail.sexo if detail else None,
        "fechaNac": str(detail.fecha_nac) if detail and detail.fecha_nac else None,
        "cdLaboral": detail.cd_laboral if detail else None,
        "areaClinica": {"id": area.id, "name": area.name} if area else None,
        "escolaridad": {"id": escolaridad.id, "name": escolaridad.name, "isActive": escolaridad.is_active} if escolaridad else None,
        "escuela": {"id": escuela.id, "name": escuela.name, "code": escuela.code, "isActive": escuela.is_active} if escuela else None,
        "tipoPersonal": base.get("tipoPersonal"),
        "termsAccepted": bool(user.terminos_acept),
        "mustChangePassword": bool(user.cambiar_clave),
        "lastLoginAt": _to_utc_iso(user.last_conexion),
        "lastIp": user.ip_ultima,
        "createdAt": _to_utc_iso(user.fch_alta),
        "createdBy": _user_ref_by_id(user.usr_alta_id, fallback_system=True),
        "updatedAt": _to_utc_iso(user.fch_modf),
        "updatedBy": _user_ref_by_id(user.usr_modf_id),
    }


def _split_permission_code(code):
    parts = code.split(":")
    if len(parts) < 2:
        return None, None
    return ":".join(parts[:-1]), parts[-1]


def _ensure_read_dependencies(permission_ids):
    permissions = {
        permission.id_permiso: permission
        for permission in Permisos.objects.filter(
            id_permiso__in=permission_ids, is_active=True
        )
    }
    expanded = set(permission_ids)

    by_code = {permission.codigo: permission for permission in permissions.values()}

    for permission in list(permissions.values()):
        resource, action = _split_permission_code(permission.codigo)
        if action in {"create", "update", "delete"} and resource:
            read_code = f"{resource}:read"
            read_permission = by_code.get(read_code)
            if read_permission:
                expanded.add(read_permission.id_permiso)

    return expanded


def _scope_error(request, code, message, details=None):
    return error_response(
        code,
        message,
        status.HTTP_403_FORBIDDEN,
        details=details,
        request_id=_request_id(request),
    )


def _validate_role_permission_scope(
    request, actor, role, actor_permissions, requested_codes=None
):
    has_wildcard = "*" in actor_permissions

    if role.es_sistema and not has_wildcard:
        return _scope_error(
            request,
            "ROLE_SYSTEM_PROTECTED",
            "No puedes modificar permisos de un rol de sistema",
        )

    if role.is_admin and not has_wildcard:
        return _scope_error(
            request,
            "ROLE_ADMIN_PROTECTED",
            "No puedes modificar permisos de un rol administrador",
        )

    has_role_assigned = RelUsuarioRol.objects.filter(
        id_usuario=actor,
        id_rol=role,
        fch_baja__isnull=True,
    ).exists()
    if has_role_assigned and not has_wildcard:
        return _scope_error(
            request,
            "SELF_ROLE_PERMISSION_ASSIGNMENT_FORBIDDEN",
            "No puedes modificar permisos de tus propios roles",
        )

    if requested_codes and not has_wildcard:
        disallowed_codes = sorted(
            code for code in requested_codes if code not in actor_permissions
        )
        if disallowed_codes:
            return _scope_error(
                request,
                "PERMISSION_GRANT_NOT_ALLOWED",
                "No puedes asignar permisos que no tienes",
                details={"permissionCodes": disallowed_codes},
            )

    return None


def _validate_user_override_scope(
    request, actor, target_user, permission, actor_permissions
):
    has_wildcard = "*" in actor_permissions

    if permission.es_sistema and not has_wildcard:
        return _scope_error(
            request,
            "PERMISSION_SYSTEM_PROTECTED",
            "No puedes gestionar overrides para un permiso de sistema",
        )

    if target_user.id_usuario == actor.id_usuario and not has_wildcard:
        return _scope_error(
            request,
            "SELF_OVERRIDE_FORBIDDEN",
            "No puedes gestionar overrides sobre tu propio usuario",
        )

    if permission.codigo not in actor_permissions and not has_wildcard:
        return _scope_error(
            request,
            "PERMISSION_GRANT_NOT_ALLOWED",
            "No puedes gestionar overrides para permisos que no tienes",
            details={"permissionCodes": [permission.codigo]},
        )

    return None


def _authorize(request, permission_code=None, require_csrf=False):
    request_id = _request_id(request)
    try:
        user = authenticate_request(request)
    except AuthServiceError as exc:
        return None, error_response(
            exc.code,
            exc.message,
            exc.status_code,
            details=exc.details,
            request_id=request_id,
        )

    request.user = user

    if permission_code:
        permissions = UserRepository.build_auth_user(user).get("permissions", [])
        if "*" not in permissions and permission_code not in permissions:
            return user, error_response(
                "PERMISSION_DENIED",
                "No tienes permiso para esta accion",
                status.HTTP_403_FORBIDDEN,
                request_id=request_id,
            )

    if require_csrf and not validate_csrf(request):
        return user, error_response(
            "PERMISSION_DENIED",
            "No tienes permiso para esta accion",
            status.HTTP_403_FORBIDDEN,
            request_id=request_id,
        )

    return user, None


def _audit(
    request,
    action,
    resource_type,
    resource_id=None,
    result="SUCCESS",
    error_code=None,
    before=None,
    after=None,
    target_user=None,
    source="legacy",
):
    actor = (
        request.user
        if getattr(request, "user", None) and request.user.is_authenticated
        else None
    )
    try:
        AuditoriaEvento.objects.create(
            request_id=_request_id(request),
            accion=action,
            recurso_tipo=resource_type,
            recurso_id=resource_id,
            actor_usuario=actor,
            actor_nombre=_user_name(actor) if actor else "Sistema",
            target_usuario=target_user,
            target_nombre=_user_name(target_user) if target_user else None,
            resultado=result,
            codigo_error=error_code,
            ip_origen=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            datos_antes=before,
            datos_despues=after,
            meta={
                "module": "rbac",
                "endpoint": request.path,
                "method": request.method,
                "source": source,
                "domain": "auth_access",
            },
        )
    except Exception:
        return


class RolesListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if _is_rbac_read_s1_enabled():
            from apps.administracion.views.rbac_read_views import RbacReadRolesListView

            return RbacReadRolesListView().get(request)

        user, auth_error = _authorize(request, "admin:gestion:roles:read")
        if auth_error:
            _audit(
                request,
                "RBAC_ROLE_LIST",
                "role",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        page, page_size, pagination_error = _parse_pagination(request)
        if pagination_error:
            _audit(
                request,
                "RBAC_ROLE_LIST",
                "role",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return pagination_error

        queryset = Roles.objects.all()

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(rol__icontains=search) | Q(desc_rol__icontains=search)
            )

        is_active_raw = _parse_bool(request.query_params.get("isActive"))
        if is_active_raw == "invalid":
            _audit(
                request,
                "RBAC_ROLE_LIST",
                "role",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Parametro isActive invalido",
                status.HTTP_400_BAD_REQUEST,
                details={"isActive": ["Debe ser true o false"]},
                request_id=_request_id(request),
            )
        if is_active_raw is not None:
            queryset = queryset.filter(is_active=is_active_raw)

        is_system_raw = _parse_bool(request.query_params.get("isSystem"))
        if is_system_raw == "invalid":
            _audit(
                request,
                "RBAC_ROLE_LIST",
                "role",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Parametro isSystem invalido",
                status.HTTP_400_BAD_REQUEST,
                details={"isSystem": ["Debe ser true o false"]},
                request_id=_request_id(request),
            )
        if is_system_raw is not None:
            queryset = queryset.filter(es_sistema=is_system_raw)

        sort_by = request.query_params.get("sortBy", "name")
        sort_order = request.query_params.get("sortOrder", "asc")
        sort_map = {
            "name": "rol",
            "description": "desc_rol",
            "isActive": "is_active",
            "isSystem": "es_sistema",
        }
        if sort_by not in sort_map:
            _audit(
                request,
                "RBAC_ROLE_LIST",
                "role",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Parametro sortBy invalido",
                status.HTTP_400_BAD_REQUEST,
                details={"sortBy": ["Campo invalido"]},
                request_id=_request_id(request),
            )
        if sort_order not in {"asc", "desc"}:
            _audit(
                request,
                "RBAC_ROLE_LIST",
                "role",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Parametro sortOrder invalido",
                status.HTTP_400_BAD_REQUEST,
                details={"sortOrder": ["Debe ser asc o desc"]},
                request_id=_request_id(request),
            )

        order_field = sort_map[sort_by]
        if sort_order == "desc":
            order_field = f"-{order_field}"
        queryset = queryset.order_by(order_field)

        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size

        items = [_serialize_role(role) for role in queryset[start:end]]
        payload = {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
        }
        _audit(request, "RBAC_ROLE_LIST", "role", result="SUCCESS")
        return Response(payload, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        if _is_rbac_role_mutation_s2_enabled():
            from apps.administracion.views.rbac_role_mutation_views import (
                RbacRoleMutationCreateView,
            )

            return RbacRoleMutationCreateView().post(request)

        user, auth_error = _authorize(
            request,
            "admin:gestion:roles:create",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_ROLE_CREATE",
                "role",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        name = request.data.get("name")
        description = request.data.get("description")
        landing_route = request.data.get("landingRoute")

        if not name or not description:
            _audit(
                request,
                "RBAC_ROLE_CREATE",
                "role",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Datos de entrada invalidos",
                status.HTTP_400_BAD_REQUEST,
                details={
                    "name": ["Campo requerido"] if not name else [],
                    "description": ["Campo requerido"] if not description else [],
                },
                request_id=_request_id(request),
            )

        if Roles.objects.filter(rol=name).exists():
            _audit(
                request,
                "RBAC_ROLE_CREATE",
                "role",
                result="FAIL",
                error_code="ROLE_EXISTS",
            )
            return error_response(
                "ROLE_EXISTS",
                "El rol ya existe",
                status.HTTP_409_CONFLICT,
                request_id=_request_id(request),
            )

        role = Roles.objects.create(
            rol=name,
            desc_rol=description,
            landing_route=landing_route,
            is_active=True,
            created_by_id=user.id_usuario,
        )

        _audit(
            request,
            "RBAC_ROLE_CREATE",
            "role",
            resource_id=role.id_rol,
            result="SUCCESS",
            after={"name": role.rol, "description": role.desc_rol},
        )
        return Response(
            {"id": role.id_rol, "name": role.rol}, status=status.HTTP_201_CREATED
        )


class RoleDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def _get_role(self, role_id):
        return Roles.objects.filter(id_rol=role_id).first()

    def get(self, request, role_id):
        if _is_rbac_read_s1_enabled():
            from apps.administracion.views.rbac_read_views import RbacReadRoleDetailView

            return RbacReadRoleDetailView().get(request, role_id)

        _, auth_error = _authorize(request, "admin:gestion:roles:read")
        if auth_error:
            _audit(
                request,
                "RBAC_ROLE_DETAIL",
                "role",
                resource_id=role_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        role = self._get_role(role_id)
        if not role:
            _audit(
                request,
                "RBAC_ROLE_DETAIL",
                "role",
                resource_id=role_id,
                result="FAIL",
                error_code="ROLE_NOT_FOUND",
            )
            return error_response(
                "ROLE_NOT_FOUND",
                "Rol no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        payload = {
            "role": _serialize_role(role),
            "permissions": _role_permissions(role),
        }
        _audit(
            request,
            "RBAC_ROLE_DETAIL",
            "role",
            resource_id=role.id_rol,
            result="SUCCESS",
        )
        return Response(payload, status=status.HTTP_200_OK)

    @transaction.atomic
    def put(self, request, role_id):
        if _is_rbac_role_mutation_s2_enabled():
            from apps.administracion.views.rbac_role_mutation_views import (
                RbacRoleMutationUpdateView,
            )

            return RbacRoleMutationUpdateView().put(request, role_id)

        user, auth_error = _authorize(
            request,
            "admin:gestion:roles:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_ROLE_UPDATE",
                "role",
                resource_id=role_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        role = self._get_role(role_id)
        if not role:
            _audit(
                request,
                "RBAC_ROLE_UPDATE",
                "role",
                resource_id=role_id,
                result="FAIL",
                error_code="ROLE_NOT_FOUND",
            )
            return error_response(
                "ROLE_NOT_FOUND",
                "Rol no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        if role.es_sistema:
            _audit(
                request,
                "RBAC_ROLE_UPDATE",
                "role",
                resource_id=role.id_rol,
                result="FAIL",
                error_code="ROLE_SYSTEM_PROTECTED",
            )
            return error_response(
                "ROLE_SYSTEM_PROTECTED",
                "El rol de sistema no puede modificarse",
                status.HTTP_403_FORBIDDEN,
                request_id=_request_id(request),
            )

        before = _serialize_role(role)

        name = request.data.get("name")
        if name and Roles.objects.filter(rol=name).exclude(id_rol=role.id_rol).exists():
            _audit(
                request,
                "RBAC_ROLE_UPDATE",
                "role",
                resource_id=role.id_rol,
                result="FAIL",
                error_code="ROLE_EXISTS",
            )
            return error_response(
                "ROLE_EXISTS",
                "El rol ya existe",
                status.HTTP_409_CONFLICT,
                request_id=_request_id(request),
            )

        if "name" in request.data:
            role.rol = name
        if "description" in request.data:
            role.desc_rol = request.data.get("description")
        if "landingRoute" in request.data:
            role.landing_route = request.data.get("landingRoute")
        if "isActive" in request.data:
            role.is_active = bool(request.data.get("isActive"))

        role.updated_at = timezone.now()
        role.updated_by_id = user.id_usuario
        role.save()
        after = _serialize_role(role)

        if after != before:
            touch_users_auth_revision(
                _active_user_ids_for_role(role),
                actor_id=user.id_usuario,
            )

        _audit(
            request,
            "RBAC_ROLE_UPDATE",
            "role",
            resource_id=role.id_rol,
            result="SUCCESS",
            before=before,
            after=after,
        )
        return Response({"role": after}, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request, role_id):
        if _is_rbac_role_mutation_s2_enabled():
            from apps.administracion.views.rbac_role_mutation_views import (
                RbacRoleMutationDeleteView,
            )

            return RbacRoleMutationDeleteView().delete(request, role_id)

        user, auth_error = _authorize(
            request,
            "admin:gestion:roles:delete",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_ROLE_DELETE",
                "role",
                resource_id=role_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        role = self._get_role(role_id)
        if not role:
            _audit(
                request,
                "RBAC_ROLE_DELETE",
                "role",
                resource_id=role_id,
                result="FAIL",
                error_code="ROLE_NOT_FOUND",
            )
            return error_response(
                "ROLE_NOT_FOUND",
                "Rol no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        if role.es_sistema:
            _audit(
                request,
                "RBAC_ROLE_DELETE",
                "role",
                resource_id=role.id_rol,
                result="FAIL",
                error_code="CANNOT_DELETE_SYSTEM_ROLE",
            )
            return error_response(
                "CANNOT_DELETE_SYSTEM_ROLE",
                "No se puede eliminar un rol de sistema",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )

        if RelUsuarioRol.objects.filter(
            id_rol=role, fch_baja__isnull=True, id_usuario__est_activo=True
        ).exists():
            _audit(
                request,
                "RBAC_ROLE_DELETE",
                "role",
                resource_id=role.id_rol,
                result="FAIL",
                error_code="ROLE_HAS_USERS",
            )
            return error_response(
                "ROLE_HAS_USERS",
                "El rol tiene usuarios activos asignados",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )

        before = _serialize_role(role)
        role.is_active = False
        role.deleted_at = timezone.now()
        role.deleted_by_id = user.id_usuario
        role.save(update_fields=["is_active", "deleted_at", "deleted_by_id"])

        touch_users_auth_revision(
            _active_user_ids_for_role(role),
            actor_id=user.id_usuario,
        )

        _audit(
            request,
            "RBAC_ROLE_DELETE",
            "role",
            resource_id=role.id_rol,
            result="SUCCESS",
            before=before,
            after={"isActive": False},
        )
        return Response({"success": True}, status=status.HTTP_200_OK)


class PermissionsCatalogView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if _is_rbac_read_s1_enabled():
            from apps.administracion.views.rbac_read_views import (
                RbacReadPermissionsCatalogView,
            )

            return RbacReadPermissionsCatalogView().get(request)

        _, auth_error = _authorize(request, "admin:gestion:permisos:read")
        if auth_error:
            _audit(
                request,
                "RBAC_PERMISSION_LIST",
                "permission",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        permissions = [
            _serialize_permission(permission)
            for permission in Permisos.objects.filter(is_active=True).order_by("codigo")
        ]
        payload = {"items": permissions, "total": len(permissions)}
        _audit(request, "RBAC_PERMISSION_LIST", "permission", result="SUCCESS")
        return Response(payload, status=status.HTTP_200_OK)


class AssignRolePermissionsView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        if _is_rbac_role_permission_s3_enabled():
            from apps.administracion.views.rbac_role_permission_views import (
                RbacRolePermissionAssignView,
            )

            return RbacRolePermissionAssignView().post(request)
        from apps.administracion.views.rbac_role_permission_legacy_views import (
            RbacRolePermissionLegacyAssignView,
        )

        return RbacRolePermissionLegacyAssignView().post(request)


class RevokeRolePermissionView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def delete(self, request, role_id, permission_id):
        if _is_rbac_role_permission_s3_enabled():
            from apps.administracion.views.rbac_role_permission_views import (
                RbacRolePermissionRevokeView,
            )

            return RbacRolePermissionRevokeView().delete(request, role_id, permission_id)
        from apps.administracion.views.rbac_role_permission_legacy_views import (
            RbacRolePermissionLegacyRevokeView,
        )

        return RbacRolePermissionLegacyRevokeView().delete(request, role_id, permission_id)


class UsersListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, "admin:gestion:usuarios:read")
        if auth_error:
            _audit(
                request,
                "RBAC_USER_LIST",
                "user",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        page, page_size, pagination_error = _parse_pagination(request)
        if pagination_error:
            _audit(
                request,
                "RBAC_USER_LIST",
                "user",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return pagination_error

        queryset = SyUsuario.objects.select_related(
            "detalle", "detalle__id_centro_atencion",
            "detalle__id_area_clinica", "detalle__id_escolaridad", "detalle__id_escuela",
        ).all()

        search = request.query_params.get("search")
        queryset = _apply_user_search_filter(queryset, search)

        is_active_raw = _parse_bool(request.query_params.get("isActive"))
        if is_active_raw == "invalid":
            _audit(
                request,
                "RBAC_USER_LIST",
                "user",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Parametro isActive invalido",
                status.HTTP_400_BAD_REQUEST,
                details={"isActive": ["Debe ser true o false"]},
                request_id=_request_id(request),
            )
        if is_active_raw is not None:
            queryset = queryset.filter(est_activo=is_active_raw)

        role_id = request.query_params.get("roleId")
        if role_id:
            queryset = queryset.filter(
                relusuariorol__id_rol_id=role_id, relusuariorol__fch_baja__isnull=True
            )

        clinic_id = request.query_params.get("clinicId")
        if clinic_id:
            queryset = queryset.filter(detalle__id_centro_atencion_id=clinic_id)

        status_filter = request.query_params.get("status")
        if status_filter == "active":
            queryset = queryset.filter(est_activo=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(est_activo=False)
        elif status_filter == "pending":
            queryset = queryset.filter(Q(terminos_acept=False) | Q(cambiar_clave=True))

        tipo_personal_id = request.query_params.get("tipoPersonalId")
        if tipo_personal_id:
            queryset = queryset.filter(detalle__id_tipo_personal_id=tipo_personal_id)

        no_exp = request.query_params.get("noExp")
        if no_exp:
            queryset = queryset.filter(detalle__no_exp__icontains=no_exp)

        user_ids_queryset = (
            queryset.order_by("usuario", "id_usuario")
            .values_list("id_usuario", flat=True)
            .distinct()
        )

        total = user_ids_queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        page_user_ids = list(user_ids_queryset[start:end])
        users_by_id = {
            user.id_usuario: user
            for user in SyUsuario.objects.select_related(
                "detalle", "detalle__id_centro_atencion", "detalle__id_area_clinica",
                "detalle__id_escolaridad", "detalle__id_escuela", "detalle__id_tipo_personal",
            ).prefetch_related("cedulas", _ROLES_PREFETCH).filter(id_usuario__in=page_user_ids)
        }
        ordered_users = [
            users_by_id[user_id] for user_id in page_user_ids if user_id in users_by_id
        ]
        items = [_serialize_user_list_item(user) for user in ordered_users]
        payload = {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
        }
        _audit(request, "RBAC_USER_LIST", "user", result="SUCCESS")
        return Response(payload, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:create",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_CREATE",
                "user",
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        required_fields = [
            "username",
            "firstName",
            "paternalName",
            "primaryRoleId",
        ]
        missing = [field for field in required_fields if not request.data.get(field)]
        if missing:
            _audit(
                request,
                "RBAC_USER_CREATE",
                "user",
                result="FAIL",
                error_code="VALIDATION_ERROR",
            )
            return error_response(
                "VALIDATION_ERROR",
                "Datos de entrada invalidos",
                status.HTTP_400_BAD_REQUEST,
                details={field: ["Campo requerido"] for field in missing},
                request_id=_request_id(request),
            )

        username = request.data.get("username")
        # Correo opcional: "" y None se tratan igual -- nunca se compara ni se
        # persiste como string vacio (rompería el unique index con otros
        # usuarios sin correo).
        email = request.data.get("email") or None

        duplicate_username = SyUsuario.objects.filter(usuario=username).exists()
        duplicate_email = bool(email) and SyUsuario.objects.filter(correo=email).exists()
        if duplicate_username or duplicate_email:
            _audit(
                request,
                "RBAC_USER_CREATE",
                "user",
                result="FAIL",
                error_code="USER_EXISTS",
            )
            return error_response(
                "USER_EXISTS",
                "Ya existe un usuario con estos datos",
                status.HTTP_409_CONFLICT,
                request_id=_request_id(request),
            )

        role = Roles.objects.filter(
            id_rol=request.data.get("primaryRoleId"), is_active=True
        ).first()
        if not role:
            _audit(
                request,
                "RBAC_USER_CREATE",
                "user",
                result="FAIL",
                error_code="ROLE_NOT_FOUND",
            )
            return error_response(
                "ROLE_NOT_FOUND",
                "Rol no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        clinic = None
        clinic_id = request.data.get("clinicId")
        if clinic_id is not None:
            clinic = CatCentroAtencion.objects.filter(
                id=clinic_id, is_active=True
            ).first()
            if not clinic:
                _audit(
                    request,
                    "RBAC_USER_CREATE",
                    "user",
                    result="FAIL",
                    error_code="CLINIC_NOT_FOUND",
                )
                return error_response(
                    "CLINIC_NOT_FOUND",
                    "Clinica no encontrada",
                    status.HTTP_404_NOT_FOUND,
                    request_id=_request_id(request),
                )

        maternal_name = request.data.get("maternalName") or ""

        area_clinica = None
        area_clinica_id = request.data.get("areaClinicaId")
        if area_clinica_id is not None:
            area_clinica = CatAreaClinica.objects.filter(
                id=area_clinica_id, is_active=True
            ).first()

        escolaridad = None
        escolaridad_id = request.data.get("escolaridadId")
        if escolaridad_id is not None:
            from apps.catalogos.models import Escolaridad
            escolaridad = Escolaridad.objects.filter(id=escolaridad_id).first()

        escuela = None
        escuela_id = request.data.get("escuelaId")
        if escuela_id is not None:
            from apps.catalogos.models import Escuelas
            escuela = Escuelas.objects.filter(id=escuela_id).first()

        tipo_personal_obj = None
        tipo_personal_id = request.data.get("tipoPersonalId")
        if tipo_personal_id is not None:
            from apps.catalogos.models import CatTipoPersonal
            tipo_personal_obj = CatTipoPersonal.objects.filter(id=tipo_personal_id).first()

        cedulas_data = request.data.get("cedulas") or []
        cedula_inputs = []
        if cedulas_data:
            if len(cedulas_data) > 3:
                return error_response(
                    "CEDULAS_LIMIT_EXCEEDED",
                    "Solo se permiten hasta 3 cédulas por usuario",
                    status.HTTP_400_BAD_REQUEST,
                    request_id=_request_id(request),
                )
            for idx, cedula_item in enumerate(cedulas_data):
                if not cedula_item.get("numero", "").strip():
                    return error_response(
                        "VALIDATION_ERROR",
                        f"La cédula {idx + 1} debe tener un número válido",
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )
                tipo_val = (cedula_item.get("tipo") or "").strip()
                if not tipo_val:
                    return error_response(
                        "VALIDATION_ERROR",
                        f"La cédula {idx + 1} debe tener un tipo",
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )
                if len(tipo_val) > 80:
                    return error_response(
                        "VALIDATION_ERROR",
                        f"El tipo de la cédula {idx + 1} es demasiado largo (máx. 80 caracteres)",
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )
            principal_count = sum(1 for c in cedulas_data if c.get("esPrincipal", False))
            if principal_count > 1:
                return error_response(
                    "VALIDATION_ERROR",
                    "Solo puede haber una cédula principal",
                    status.HTTP_400_BAD_REQUEST,
                    request_id=_request_id(request),
                )
            cedula_inputs = [
                CedulaInput(
                    numero=cedula_item["numero"].strip(),
                    tipo=(cedula_item.get("tipo") or "").strip(),
                    es_principal=bool(cedula_item.get("esPrincipal", False)),
                )
                for cedula_item in cedulas_data
            ]

        result = CreateUserUseCase.execute(
            CreateUserData(
                username=username,
                first_name=request.data.get("firstName"),
                paternal_name=request.data.get("paternalName"),
                maternal_name=maternal_name,
                email=email,
                role=role,
                actor=actor,
                clinic=clinic,
                no_exp=request.data.get("noExp") or None,
                cd_laboral=request.data.get("cdLaboral") or None,
                telefono=request.data.get("telefono") or None,
                sexo=request.data.get("sexo") or None,
                fecha_nac=request.data.get("fechaNac") or None,
                area_clinica=area_clinica,
                escolaridad=escolaridad,
                escuela=escuela,
                tipo_personal=tipo_personal_obj,
                cedulas=cedula_inputs,
            )
        )
        user = result.user

        # `credentials_email_sent` es None cuando el usuario se creo SIN
        # correo -- ahi nunca se intento enviar nada, no es un fallo y no
        # dispara rollback. Cuando SI hay correo, se conserva el
        # comportamiento existente gobernado por ALLOW_USER_CREATE_WITHOUT_EMAIL.
        if (
            result.credentials_email_sent is False
            and not settings.ALLOW_USER_CREATE_WITHOUT_EMAIL
        ):
            transaction.set_rollback(True)
            _audit(
                request,
                "RBAC_USER_CREATE",
                "user",
                resource_id=user.id_usuario,
                result="FAIL",
                error_code="EMAIL_DELIVERY_FAILED",
                target_user=user,
            )
            return error_response(
                "EMAIL_DELIVERY_FAILED",
                "No se pudo enviar el correo de credenciales. El usuario no fue creado.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=_request_id(request),
            )

        credentials_email_sent = bool(result.credentials_email_sent)
        payload = {
            "id": user.id_usuario,
            "username": user.usuario,
            "credentialsEmailSent": credentials_email_sent,
        }
        audit_after = {
            "username": user.usuario,
            "credentialsEmailSent": credentials_email_sent,
        }
        _audit(
            request,
            "RBAC_USER_CREATE",
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            after=audit_after,
            target_user=user,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def _get_user(self, user_id):
        return (
            SyUsuario.objects.select_related(
                "detalle",
                "detalle__id_centro_atencion",
                "detalle__id_area_clinica",
                "detalle__id_escolaridad",
                "detalle__id_escuela",
                "detalle__id_tipo_personal",
                "perfil_medico",
                "perfil_medico__id_especialidad",
                "perfil_enfermeria",
                "perfil_enfermeria__id_area_clinica",
                "perfil_administrativo",
            )
            .prefetch_related("cedulas", _ROLES_PREFETCH)
            .filter(id_usuario=user_id)
            .first()
        )

    def get(self, request, user_id):
        _, auth_error = _authorize(request, "admin:gestion:usuarios:read")
        if auth_error:
            _audit(
                request,
                "RBAC_USER_DETAIL",
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        user = self._get_user(user_id)
        if not user:
            _audit(
                request,
                "RBAC_USER_DETAIL",
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code="USER_NOT_FOUND",
            )
            return error_response(
                "USER_NOT_FOUND",
                "Usuario no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        payload = {
            "user": _serialize_user_detail(user),
            "roles": _serialize_user_roles(user),
            "overrides": _serialize_user_overrides(user),
        }
        _audit(
            request,
            "RBAC_USER_DETAIL",
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            target_user=user,
        )
        return Response(payload, status=status.HTTP_200_OK)

    @transaction.atomic
    def patch(self, request, user_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_UPDATE",
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        user = self._get_user(user_id)
        if not user:
            _audit(
                request,
                "RBAC_USER_UPDATE",
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code="USER_NOT_FOUND",
            )
            return error_response(
                "USER_NOT_FOUND",
                "Usuario no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        before = _serialize_user_detail(user)

        detail = getattr(user, "detalle", None)
        if not detail:
            detail = DetUsuario.objects.create(
                id_usuario=user,
                nombre="",
                paterno="",
                materno="",
            )

        if "email" in request.data:
            # Correo opcional: "" y None se tratan igual -- nunca se compara
            # ni se persiste como string vacio (rompería el unique index con
            # otros usuarios sin correo).
            email = request.data.get("email") or None
            if (
                email
                and SyUsuario.objects.filter(correo=email)
                .exclude(id_usuario=user.id_usuario)
                .exists()
            ):
                _audit(
                    request,
                    "RBAC_USER_UPDATE",
                    "user",
                    resource_id=user.id_usuario,
                    result="FAIL",
                    error_code="USER_EXISTS",
                    target_user=user,
                )
                return error_response(
                    "USER_EXISTS",
                    "Ya existe un usuario con estos datos",
                    status.HTTP_409_CONFLICT,
                    request_id=_request_id(request),
                )
            user.correo = email

        if "firstName" in request.data:
            detail.nombre = request.data.get("firstName") or ""
        if "paternalName" in request.data:
            paternal_name = request.data.get("paternalName")
            if not paternal_name:
                _audit(
                    request,
                    "RBAC_USER_UPDATE",
                    "user",
                    resource_id=user.id_usuario,
                    result="FAIL",
                    error_code="VALIDATION_ERROR",
                    target_user=user,
                )
                return error_response(
                    "VALIDATION_ERROR",
                    "Datos de entrada invalidos",
                    status.HTTP_400_BAD_REQUEST,
                    details={"paternalName": ["Apellido Paterno es obligatorio"]},
                    request_id=_request_id(request),
                )
            detail.paterno = paternal_name
        if "maternalName" in request.data:
            detail.materno = request.data.get("maternalName") or ""

        if "clinicId" in request.data:
            clinic_id = request.data.get("clinicId")
            if clinic_id is None:
                detail.id_centro_atencion = None
            else:
                clinic = CatCentroAtencion.objects.filter(
                    id=clinic_id, is_active=True
                ).first()
                if not clinic:
                    _audit(
                        request,
                        "RBAC_USER_UPDATE",
                        "user",
                        resource_id=user.id_usuario,
                        result="FAIL",
                        error_code="CLINIC_NOT_FOUND",
                        target_user=user,
                    )
                    return error_response(
                        "CLINIC_NOT_FOUND",
                        "Clinica no encontrada",
                        status.HTTP_404_NOT_FOUND,
                        request_id=_request_id(request),
                    )
                detail.id_centro_atencion = clinic

        if "noExp" in request.data:
            detail.no_exp = request.data.get("noExp") or None

        if "cdLaboral" in request.data:
            detail.cd_laboral = request.data.get("cdLaboral") or None

        if "telefono" in request.data:
            detail.telefono = request.data.get("telefono") or None

        if "sexo" in request.data:
            detail.sexo = request.data.get("sexo") or None

        if "fechaNac" in request.data:
            detail.fecha_nac = request.data.get("fechaNac") or None

        if "escolaridadId" in request.data:
            esc_id = request.data.get("escolaridadId")
            if esc_id is None:
                detail.id_escolaridad = None
            else:
                from apps.catalogos.models import Escolaridad
                detail.id_escolaridad = Escolaridad.objects.filter(id=esc_id).first()

        if "escuelaId" in request.data:
            esc_id = request.data.get("escuelaId")
            if esc_id is None:
                detail.id_escuela = None
            else:
                from apps.catalogos.models import Escuelas
                detail.id_escuela = Escuelas.objects.filter(id=esc_id).first()

        if "tipoPersonalId" in request.data:
            tp_id = request.data.get("tipoPersonalId")
            if tp_id is None:
                detail.id_tipo_personal = None
            else:
                from apps.catalogos.models import CatTipoPersonal
                detail.id_tipo_personal = CatTipoPersonal.objects.filter(id=tp_id).first()

        if "areaClinicaId" in request.data:
            area_id = request.data.get("areaClinicaId")
            if area_id is None:
                detail.id_area_clinica = None
            else:
                area = CatAreaClinica.objects.filter(id=area_id, is_active=True).first()
                if not area:
                    _audit(
                        request,
                        "RBAC_USER_UPDATE",
                        "user",
                        resource_id=user.id_usuario,
                        result="FAIL",
                        error_code="AREA_CLINICA_NOT_FOUND",
                        target_user=user,
                    )
                    return error_response(
                        "AREA_CLINICA_NOT_FOUND",
                        "Área clínica no encontrada",
                        status.HTTP_404_NOT_FOUND,
                        request_id=_request_id(request),
                    )
                detail.id_area_clinica = area

        detail.save()

        if "cedulas" in request.data:
            cedulas_data = request.data.get("cedulas") or []
            if len(cedulas_data) > 3:
                return error_response(
                    "CEDULAS_LIMIT_EXCEEDED",
                    "Solo se permiten hasta 3 cédulas por usuario",
                    status.HTTP_400_BAD_REQUEST,
                    request_id=_request_id(request),
                )
            for idx, cedula_item in enumerate(cedulas_data):
                if not cedula_item.get("numero", "").strip():
                    return error_response(
                        "VALIDATION_ERROR",
                        f"La cédula {idx + 1} debe tener un número válido",
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )
                tipo_val = (cedula_item.get("tipo") or "").strip()
                if not tipo_val:
                    return error_response(
                        "VALIDATION_ERROR",
                        f"La cédula {idx + 1} debe tener un tipo",
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )
                if len(tipo_val) > 80:
                    return error_response(
                        "VALIDATION_ERROR",
                        f"El tipo de la cédula {idx + 1} es demasiado largo (máx. 80 caracteres)",
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )

            principal_count = sum(
                1 for c in cedulas_data if c.get("esPrincipal", False)
            )
            if principal_count > 1:
                return error_response(
                    "VALIDATION_ERROR",
                    "Solo puede haber una cédula principal",
                    status.HTTP_400_BAD_REQUEST,
                    request_id=_request_id(request),
                )

            user.cedulas.all().delete()
            for idx, cedula_item in enumerate(cedulas_data):
                DetUsuarioCedula.objects.create(
                    id_usuario=user,
                    numero=cedula_item["numero"].strip(),
                    tipo=(cedula_item.get("tipo") or "").strip(),
                    es_principal=bool(cedula_item.get("esPrincipal", False)),
                    orden=idx + 1,
                )

        for field_name, apply_fn in (
            ("perfilMedico", _apply_perfil_medico),
            ("perfilEnfermeria", _apply_perfil_enfermeria),
            ("perfilAdministrativo", _apply_perfil_administrativo),
        ):
            if field_name in request.data:
                perfil_error = apply_fn(user, request.data.get(field_name), actor)
                if perfil_error:
                    error_code, error_message = perfil_error
                    _audit(
                        request,
                        "RBAC_USER_UPDATE",
                        "user",
                        resource_id=user.id_usuario,
                        result="FAIL",
                        error_code=error_code,
                        target_user=user,
                    )
                    return error_response(
                        error_code,
                        error_message,
                        status.HTTP_400_BAD_REQUEST,
                        request_id=_request_id(request),
                    )

        user.fch_modf = timezone.now()
        user.usr_modf = actor
        user.save(update_fields=["correo", "fch_modf", "usr_modf"])

        # Recargar para que la respuesta refleje perfiles recien creados/editados
        # (get_or_create arriba no actualiza los related_name cacheados en `user`).
        user = self._get_user(user.id_usuario)

        payload = {"user": _serialize_user_detail(user)}
        _audit(
            request,
            "RBAC_USER_UPDATE",
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            before=before,
            after=payload,
            target_user=user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class UserStatusView(APIView):
    authentication_classes = []
    permission_classes = []
    activate = True

    @transaction.atomic
    def patch(self, request, user_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        action = "RBAC_USER_ACTIVATE" if self.activate else "RBAC_USER_DEACTIVATE"
        if auth_error:
            _audit(
                request,
                action,
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        user = SyUsuario.objects.filter(id_usuario=user_id).first()
        if not user:
            _audit(
                request,
                action,
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code="USER_NOT_FOUND",
            )
            return error_response(
                "USER_NOT_FOUND",
                "Usuario no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        if not self.activate and actor.id_usuario == user.id_usuario:
            _audit(
                request,
                action,
                "user",
                resource_id=user.id_usuario,
                result="FAIL",
                error_code="SELF_DEACTIVATION_NOT_ALLOWED",
                target_user=user,
            )
            return error_response(
                "SELF_DEACTIVATION_NOT_ALLOWED",
                "No puedes desactivar tu propia cuenta",
                status.HTTP_409_CONFLICT,
                request_id=_request_id(request),
            )

        user.est_activo = self.activate
        user.fch_modf = timezone.now()
        user.usr_modf = actor
        user.save(update_fields=["est_activo", "fch_modf", "usr_modf"])

        payload = {"id": user.id_usuario, "isActive": bool(user.est_activo)}
        _audit(
            request,
            action,
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            after=payload,
            target_user=user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class UserActivateView(UserStatusView):
    activate = True


class UserDeactivateView(UserStatusView):
    activate = False


class UserResetPasswordView(APIView):
    # Reset administrativo de contraseña: metodo de fallback para cuando no
    # hay internet (no se puede enviar correo) pero si hay acceso al
    # sistema/base de datos. Genera una password temporal nueva y la
    # devuelve en texto plano en la respuesta HTTP -- unico lugar donde esa
    # password existe en texto plano, de forma transitoria. NUNCA se envia
    # por correo ni se loguea en claro (ver `_audit` mas abajo).
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, user_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_PASSWORD_RESET",
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        user = SyUsuario.objects.filter(id_usuario=user_id).first()
        if not user:
            _audit(
                request,
                "RBAC_USER_PASSWORD_RESET",
                "user",
                resource_id=user_id,
                result="FAIL",
                error_code="USER_NOT_FOUND",
            )
            return error_response(
                "USER_NOT_FOUND",
                "Usuario no encontrado",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        if actor.id_usuario == user.id_usuario:
            _audit(
                request,
                "RBAC_USER_PASSWORD_RESET",
                "user",
                resource_id=user.id_usuario,
                result="FAIL",
                error_code="SELF_PASSWORD_RESET_NOT_ALLOWED",
                target_user=user,
            )
            return error_response(
                "SELF_PASSWORD_RESET_NOT_ALLOWED",
                "No puedes restablecer tu propia contraseña por esta vía",
                status.HTTP_409_CONFLICT,
                request_id=_request_id(request),
            )

        temporary_password = generate_temporary_password()
        user.clave_hash = make_password(temporary_password)
        user.cambiar_clave = True
        user.fch_modf = timezone.now()
        user.usr_modf = actor
        user.save(
            update_fields=["clave_hash", "cambiar_clave", "fch_modf", "usr_modf"]
        )

        _audit(
            request,
            "RBAC_USER_PASSWORD_RESET",
            "user",
            resource_id=user.id_usuario,
            result="SUCCESS",
            after={"passwordReset": True},
            target_user=user,
        )
        return Response(
            {
                "temporaryPassword": temporary_password,
                "mustChangePassword": True,
            },
            status=status.HTTP_200_OK,
        )


class UserRolesView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, user_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_ROLES_ASSIGN",
                "user_role",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error
        role_ids = request.data.get("roleIds")

        try:
            result = AssignUserRolesUseCase.execute(
                actor=actor,
                user_id=user_id,
                role_ids=role_ids,
                serialize_user_roles=_serialize_user_roles,
            )
        except RbacWriteError as exc:
            _audit(
                request,
                "RBAC_USER_ROLES_ASSIGN",
                "user_role",
                resource_id=exc.resource_id,
                result="FAIL",
                error_code=exc.code,
                target_user=exc.target_user,
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=_request_id(request),
            )

        target_user = result["target_user"]
        payload = result["payload"]
        _audit(
            request,
            "RBAC_USER_ROLES_ASSIGN",
            "user_role",
            resource_id=target_user.id_usuario,
            result="SUCCESS",
            before=result["before"],
            after=payload,
            target_user=target_user,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class UserPrimaryRoleView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def put(self, request, user_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_ROLE_PRIMARY_SET",
                "user_role",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error
        role_id = request.data.get("roleId")

        try:
            result = SetUserPrimaryRoleUseCase.execute(
                actor=actor,
                user_id=user_id,
                role_id=role_id,
                serialize_user_roles=_serialize_user_roles,
            )
        except RbacWriteError as exc:
            _audit(
                request,
                "RBAC_USER_ROLE_PRIMARY_SET",
                "user_role",
                resource_id=exc.resource_id,
                result="FAIL",
                error_code=exc.code,
                target_user=exc.target_user,
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=_request_id(request),
            )

        target_user = result["target_user"]
        payload = result["payload"]
        _audit(
            request,
            "RBAC_USER_ROLE_PRIMARY_SET",
            "user_role",
            resource_id=target_user.id_usuario,
            result="SUCCESS",
            before=result["before"],
            after=payload,
            target_user=target_user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class UserRoleRevokeView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def delete(self, request, user_id, role_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_ROLE_REVOKE",
                "user_role",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        try:
            result = RevokeUserRoleUseCase.execute(
                actor=actor,
                user_id=user_id,
                role_id=role_id,
                serialize_user_roles=_serialize_user_roles,
            )
        except RbacWriteError as exc:
            _audit(
                request,
                "RBAC_USER_ROLE_REVOKE",
                "user_role",
                resource_id=exc.resource_id,
                result="FAIL",
                error_code=exc.code,
                target_user=exc.target_user,
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=_request_id(request),
            )

        target_user = result["target_user"]
        payload = result["payload"]
        _audit(
            request,
            "RBAC_USER_ROLE_REVOKE",
            "user_role",
            resource_id=target_user.id_usuario,
            result="SUCCESS",
            before=result["before"],
            after=payload,
            target_user=target_user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class UserOverridesView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, user_id):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_OVERRIDE_UPSERT",
                "user_override",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error
        permission_code = request.data.get("permissionCode")
        effect = request.data.get("effect")
        expires_at_raw = request.data.get("expiresAt")

        try:
            result = UpsertUserOverrideUseCase.execute(
                actor=actor,
                user_id=user_id,
                permission_code=permission_code,
                effect=effect,
                expires_at_raw=expires_at_raw,
                parse_expires_at=_parse_expires_at_end_of_day,
                serialize_user_overrides=_serialize_user_overrides,
            )
        except RbacWriteError as exc:
            _audit(
                request,
                "RBAC_USER_OVERRIDE_UPSERT",
                "user_override",
                resource_id=exc.resource_id,
                result="FAIL",
                error_code=exc.code,
                target_user=exc.target_user,
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=_request_id(request),
            )

        target_user = result["target_user"]
        payload = result["payload"]
        _audit(
            request,
            "RBAC_USER_OVERRIDE_UPSERT",
            "user_override",
            resource_id=target_user.id_usuario,
            result="SUCCESS",
            before=result["before"],
            after=payload,
            target_user=target_user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class UserOverrideRemoveView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def delete(self, request, user_id, code):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            _audit(
                request,
                "RBAC_USER_OVERRIDE_REMOVE",
                "user_override",
                resource_id=user_id,
                result="FAIL",
                error_code=auth_error.data.get("code"),
            )
            return auth_error

        try:
            result = RemoveUserOverrideUseCase.execute(
                actor=actor,
                user_id=user_id,
                code=code,
                serialize_user_overrides=_serialize_user_overrides,
            )
        except RbacWriteError as exc:
            _audit(
                request,
                "RBAC_USER_OVERRIDE_REMOVE",
                "user_override",
                resource_id=exc.resource_id,
                result="FAIL",
                error_code=exc.code,
                target_user=exc.target_user,
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=_request_id(request),
            )

        target_user = result["target_user"]
        payload = result["payload"]
        _audit(
            request,
            "RBAC_USER_OVERRIDE_REMOVE",
            "user_override",
            resource_id=target_user.id_usuario,
            result="SUCCESS",
            before=result["before"],
            after=payload,
            target_user=target_user,
        )
        return Response(payload, status=status.HTTP_200_OK)


class EmpleadoSermedLookupView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, no_exp):
        _, auth_error = _authorize(request, "admin:gestion:usuarios:read")
        if auth_error:
            return auth_error

        no_exp = no_exp.strip()
        if not no_exp:
            return error_response(
                "VALIDATION_ERROR",
                "Número de expediente requerido",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )

        sql = """
            SELECT
                e.NO_EXP,
                e.DS_PATERNO,
                e.DS_MATERNO,
                e.DS_NOMBRE,
                e.CD_LABORAL,
                e.CD_CLINICA
            FROM cat_empleados e
            WHERE e.NO_EXP = %s
            LIMIT 1
        """
        try:
            with connections["expedientes"].cursor() as cursor:
                cursor.execute(sql, [no_exp])
                row = cursor.fetchone()
        except Exception:
            return error_response(
                "SERMED_UNAVAILABLE",
                "No se pudo consultar la base de SERMED",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                request_id=_request_id(request),
            )

        if not row:
            return error_response(
                "EMPLEADO_NOT_FOUND",
                "No se encontró un empleado con ese número de expediente",
                status.HTTP_404_NOT_FOUND,
                request_id=_request_id(request),
            )

        payload = {
            "noExp": row[0],
            "paternalName": row[1] or "",
            "maternalName": row[2] or "",
            "firstName": row[3] or "",
            "cdLaboral": row[4] or "",
            "cdClinica": row[5] or "",
        }
        return Response({"empleado": payload}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Notificaciones masivas a usuarios
# ---------------------------------------------------------------------------

class UsersNotifyView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        actor, auth_error = _authorize(
            request,
            "admin:gestion:usuarios:update",
            require_csrf=True,
        )
        if auth_error:
            return auth_error

        subject = (request.data.get("subject") or "").strip()
        message = (request.data.get("message") or "").strip()
        category = (request.data.get("category") or "Notificación SISEM").strip()
        preview = request.query_params.get("preview") == "true"

        if not subject:
            return error_response(
                "VALIDATION_ERROR",
                "El asunto es requerido.",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )
        if not message:
            return error_response(
                "VALIDATION_ERROR",
                "El mensaje es requerido.",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )

        qs = SyUsuario.objects.select_related("detalle").filter(est_activo=True)

        cd_laboral = (request.data.get("cdLaboral") or "").strip()
        if cd_laboral:
            qs = qs.filter(detalle__cd_laboral__icontains=cd_laboral)

        user_id = request.data.get("userId")
        if user_id:
            qs = qs.filter(id_usuario=user_id)

        clinic_id = request.data.get("clinicId")
        if clinic_id:
            qs = qs.filter(detalle__id_centro_atencion_id=clinic_id)

        recipients = [
            {
                "email": u.correo,
                "username": u.usuario,
                "name": getattr(u.detalle, "nombre_completo", None) or u.usuario,
            }
            for u in qs
            if u.correo
        ]

        if not recipients:
            return error_response(
                "NO_RECIPIENTS",
                "No hay usuarios activos que coincidan con los filtros seleccionados.",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )

        if preview:
            return Response({"count": len(recipients)}, status=status.HTTP_200_OK)

        # Adjuntos opcionales (multipart/form-data)
        MAX_FILE_BYTES  = 10 * 1024 * 1024   # 10 MB por archivo
        MAX_TOTAL_BYTES = 25 * 1024 * 1024   # 25 MB total (límite Gmail)
        attachments = []
        total_size  = 0
        for uploaded in request.FILES.getlist("attachments"):
            if uploaded.size > MAX_FILE_BYTES:
                return error_response(
                    "ATTACHMENT_TOO_LARGE",
                    f"El archivo '{uploaded.name}' supera el límite de 10 MB.",
                    status.HTTP_400_BAD_REQUEST,
                    request_id=_request_id(request),
                )
            total_size += uploaded.size
            if total_size > MAX_TOTAL_BYTES:
                return error_response(
                    "ATTACHMENTS_EXCEED_LIMIT",
                    "El tamaño total de los adjuntos supera el límite de 25 MB.",
                    status.HTTP_400_BAD_REQUEST,
                    request_id=_request_id(request),
                )
            attachments.append((uploaded.name, uploaded.read(), uploaded.content_type or "application/octet-stream"))

        result = send_notification_email_batch(
            recipients=recipients,
            subject=subject,
            message=message,
            category=category,
            attachments=attachments or None,
        )
        _audit(
            request,
            "RBAC_USER_NOTIFY",
            "user",
            result="SUCCESS",
            after={"sent": result["sent"], "failed": len(result["failed"]), "subject": subject},
        )
        return Response(result, status=status.HTTP_200_OK)

# ---------------------------------------------------------------------------
# Valores distintos de cd_laboral registrados en el sistema
# ---------------------------------------------------------------------------

class UserCdLaboralesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, "admin:gestion:usuarios:read")
        if auth_error:
            return auth_error

        values = (
            DetUsuario.objects.filter(cd_laboral__isnull=False)
            .exclude(cd_laboral="")
            .values_list("cd_laboral", flat=True)
            .distinct()
            .order_by("cd_laboral")
        )
        return Response({"items": list(values)}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Exportación Excel de usuarios
# ---------------------------------------------------------------------------

class UserExportView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        actor, auth_error = _authorize(request, "admin:gestion:usuarios:read")
        if auth_error:
            return auth_error

        import io
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from django.http import HttpResponse

        # ── Mismos filtros que UsersListCreateView ──────────────────────────
        qs = SyUsuario.objects.select_related(
            "detalle",
            "detalle__id_centro_atencion",
            "detalle__id_area_clinica",
            "detalle__id_escolaridad",
            "detalle__id_escuela",
        ).prefetch_related("cedulas", _ROLES_PREFETCH).all()

        search = request.query_params.get("search")
        qs = _apply_user_search_filter(qs, search)

        is_active_raw = _parse_bool(request.query_params.get("isActive"))
        if is_active_raw not in (None, "invalid"):
            qs = qs.filter(est_activo=is_active_raw)

        role_id = request.query_params.get("roleId")
        if role_id:
            qs = qs.filter(
                relusuariorol__id_rol_id=role_id,
                relusuariorol__fch_baja__isnull=True,
            )

        clinic_id = request.query_params.get("clinicId")
        if clinic_id:
            qs = qs.filter(detalle__id_centro_atencion_id=clinic_id)

        status_filter = request.query_params.get("status")
        if status_filter == "active":
            qs = qs.filter(est_activo=True)
        elif status_filter == "inactive":
            qs = qs.filter(est_activo=False)
        elif status_filter == "pending":
            qs = qs.filter(Q(terminos_acept=False) | Q(cambiar_clave=True))

        no_exp = request.query_params.get("noExp")
        if no_exp:
            qs = qs.filter(detalle__no_exp__icontains=no_exp)

        users = list(qs.order_by("detalle__nombre_completo", "usuario").distinct())

        # ── Libro Excel ─────────────────────────────────────────────────────
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Usuarios"

        BRAND = "D94300"
        HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
        HEADER_FILL = PatternFill("solid", fgColor=BRAND)
        HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
        CELL_ALIGN = Alignment(vertical="center")
        BORDER_SIDE = Side(style="thin", color="D7DEE8")
        THIN_BORDER = Border(
            left=BORDER_SIDE, right=BORDER_SIDE,
            top=BORDER_SIDE, bottom=BORDER_SIDE,
        )

        HEADERS = [
            "Usuario",
            "Tipo personal",
            "Nombre",
            "Ap. Paterno",
            "Ap. Materno",
            "Nombre completo",
            "Correo",
            "Teléfono",
            "Sexo",
            "Fecha nacimiento",
            "No. expediente SERMED",
            "Clave laboral",
            "Centro de atención",
            "Área clínica",
            "Escolaridad",
            "Escuela (siglas)",
            "Escuela (nombre)",
            "Cédula 1",
            "Cédula 2",
            "Cédula 3",
            "Rol primario",
            "Estado",
            "Fecha de alta",
            "Fecha de modificación",
        ]

        # Encabezados
        for col_idx, header in enumerate(HEADERS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGN
            cell.border = THIN_BORDER

        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"

        # Filas de datos
        FILL_ODD = PatternFill("solid", fgColor="F8FAFC")

        for row_idx, user in enumerate(users, start=2):
            detail = getattr(user, "detalle", None)
            roles = _get_active_roles(user)
            primary = next((r for r in roles if r.is_primary), roles[0] if roles else None)
            cedulas = list(user.cedulas.all())

            if user.est_activo and getattr(user, "terminos_acept", True) and not getattr(user, "cambiar_clave", False):
                est_label = "Activo"
            elif not user.est_activo:
                est_label = "Inactivo"
            else:
                est_label = "Pendiente"

            def _cedula_str(idx):
                if idx < len(cedulas):
                    c = cedulas[idx]
                    return f"{c.numero} ({c.tipo})"
                return ""

            SEXO_LABELS = {"M": "Masculino", "F": "Femenino"}
            row_data = [
                user.usuario,
                detail.id_tipo_personal.name if detail and detail.id_tipo_personal else "",
                detail.nombre if detail else "",
                detail.paterno if detail else "",
                detail.materno if detail else "",
                detail.nombre_completo if detail else "",
                user.correo,
                detail.telefono if detail else "",
                SEXO_LABELS.get(detail.sexo, detail.sexo or "") if detail else "",
                str(detail.fecha_nac) if detail and detail.fecha_nac else "",
                detail.no_exp if detail else "",
                detail.cd_laboral if detail else "",
                detail.id_centro_atencion.name if detail and detail.id_centro_atencion else "",
                detail.id_area_clinica.name if detail and detail.id_area_clinica else "",
                detail.id_escolaridad.name if detail and detail.id_escolaridad else "",
                detail.id_escuela.code if detail and detail.id_escuela else "",
                detail.id_escuela.name if detail and detail.id_escuela else "",
                _cedula_str(0),
                _cedula_str(1),
                _cedula_str(2),
                primary.id_rol.rol if primary else "",
                est_label,
                user.fch_alta.strftime("%d/%m/%Y") if user.fch_alta else "",
                user.fch_modf.strftime("%d/%m/%Y") if user.fch_modf else "",
            ]

            fill = FILL_ODD if row_idx % 2 == 0 else None

            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.alignment = CELL_ALIGN
                cell.border = THIN_BORDER
                if fill:
                    cell.fill = fill

        # Ancho automático de columnas
        COL_MIN_WIDTH = 10
        COL_MAX_WIDTH = 40
        for col_idx in range(1, len(HEADERS) + 1):
            col_letter = get_column_letter(col_idx)
            max_len = len(HEADERS[col_idx - 1])
            for row_idx in range(2, len(users) + 2):
                cell_val = ws.cell(row=row_idx, column=col_idx).value
                if cell_val:
                    max_len = max(max_len, len(str(cell_val)))
            ws.column_dimensions[col_letter].width = min(max(max_len + 2, COL_MIN_WIDTH), COL_MAX_WIDTH)

        # Respuesta HTTP
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        from django.utils import timezone as tz
        filename = f"usuarios_{tz.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Total-Users"] = str(len(users))
        return response
