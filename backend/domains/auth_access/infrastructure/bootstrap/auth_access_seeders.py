from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from apps.administracion.models import RelRolPermiso, RelUsuarioOverride, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles


BASE_ROLES = ("admin", "user")
BASE_PERMISSIONS = ("read_users", "write_users", "delete_users", "manage_roles")


@dataclass(frozen=True)
class SeedSummary:
    created_users: int = 0
    created_roles: int = 0
    created_permissions: int = 0
    created_role_permissions: int = 0
    created_user_roles: int = 0
    created_overrides: int = 0

    def merge(self, other: "SeedSummary") -> "SeedSummary":
        return SeedSummary(
            created_users=self.created_users + other.created_users,
            created_roles=self.created_roles + other.created_roles,
            created_permissions=self.created_permissions + other.created_permissions,
            created_role_permissions=self.created_role_permissions
            + other.created_role_permissions,
            created_user_roles=self.created_user_roles + other.created_user_roles,
            created_overrides=self.created_overrides + other.created_overrides,
        )


def _upsert_role(
    *, name: str, description: str, landing_route: str, is_admin: bool = False
) -> tuple[Roles, bool]:
    role, created = Roles.objects.get_or_create(
        rol=name,
        defaults={
            "desc_rol": description,
            "landing_route": landing_route,
            "is_admin": is_admin,
            "is_active": True,
            "es_sistema": False,
            "updated_at": timezone.now(),
        },
    )
    if not created:
        needs_save = False
        if role.desc_rol != description:
            role.desc_rol = description
            needs_save = True
        if role.landing_route != landing_route:
            role.landing_route = landing_route
            needs_save = True
        if role.is_admin != is_admin:
            role.is_admin = is_admin
            needs_save = True
        if not role.is_active:
            role.is_active = True
            needs_save = True
        if needs_save:
            role.updated_at = timezone.now()
            role.save(
                update_fields=[
                    "desc_rol",
                    "landing_route",
                    "is_admin",
                    "is_active",
                    "updated_at",
                ]
            )
    return role, created


def _upsert_permission(*, code: str, description: str) -> tuple[Permisos, bool]:
    permission, created = Permisos.objects.get_or_create(
        codigo=code,
        defaults={
            "descripcion": description,
            "is_active": True,
            "es_sistema": False,
            "updated_at": timezone.now(),
        },
    )
    if not created:
        needs_save = False
        if permission.descripcion != description:
            permission.descripcion = description
            needs_save = True
        if not permission.is_active:
            permission.is_active = True
            needs_save = True
        if needs_save:
            permission.updated_at = timezone.now()
            permission.save(update_fields=["descripcion", "is_active", "updated_at"])
    return permission, created


def _upsert_user(
    *, username: str, email: str, raw_password: str, force_change_password: bool = False
) -> tuple[SyUsuario, bool]:
    user, created = SyUsuario.objects.get_or_create(
        usuario=username,
        defaults={
            "correo": email,
            "clave_hash": make_password(raw_password),
            "est_activo": True,
            "est_bloqueado": False,
            "cambiar_clave": force_change_password,
            "terminos_acept": not force_change_password,
            "fch_terminos": None if force_change_password else timezone.now(),
            "fch_modf": timezone.now(),
        },
    )
    if not created:
        user.correo = email
        user.clave_hash = make_password(raw_password)
        user.est_activo = True
        user.est_bloqueado = False
        user.cambiar_clave = force_change_password
        user.terminos_acept = not force_change_password
        user.fch_modf = timezone.now()
        user.fch_terminos = (
            None if force_change_password else (user.fch_terminos or timezone.now())
        )
        user.save(
            update_fields=[
                "correo",
                "clave_hash",
                "est_activo",
                "est_bloqueado",
                "cambiar_clave",
                "terminos_acept",
                "fch_modf",
                "fch_terminos",
            ]
        )

    DetUsuario.objects.get_or_create(
        id_usuario=user,
        defaults={
            "nombre": username.split("_")[0].capitalize(),
            "paterno": "Auth",
            "materno": "Access",
        },
    )
    return user, created


def _assign_role_to_user(*, user: SyUsuario, role: Roles, is_primary: bool) -> bool:
    relation, created = RelUsuarioRol.objects.get_or_create(
        id_usuario=user,
        id_rol=role,
        defaults={"is_primary": is_primary, "usr_asignacion": user, "fch_baja": None},
    )
    if not created and is_primary and not relation.is_primary:
        relation.is_primary = True
        relation.fch_baja = None
        relation.save(update_fields=["is_primary", "fch_baja"])
    return created


def _assign_permission_to_role(
    *, role: Roles, permission: Permisos, actor: SyUsuario | None = None
) -> bool:
    _, created = RelRolPermiso.objects.get_or_create(
        id_rol=role,
        id_permiso=permission,
        defaults={"usr_asignacion": actor, "fch_baja": None},
    )
    return created


def _create_override(
    *,
    user: SyUsuario,
    permission: Permisos,
    efecto: str = RelUsuarioOverride.Efecto.ALLOW,
) -> bool:
    _, created = RelUsuarioOverride.objects.get_or_create(
        id_usuario=user,
        id_permiso=permission,
        defaults={
            "efecto": efecto,
            "usr_asignacion": user,
            "fch_asignacion": timezone.now(),
            "fch_expira": None,
            "fch_baja": None,
        },
    )
    return created


@transaction.atomic
def seed_auth_access_base(*, admin_password: str) -> SeedSummary:
    summary = SeedSummary()

    admin_role, created = _upsert_role(
        name="admin",
        description="Administrador del dominio Auth-Access",
        landing_route="/admin",
        is_admin=True,
    )
    summary = summary.merge(SeedSummary(created_roles=1 if created else 0))

    user_role, created = _upsert_role(
        name="user",
        description="Usuario base del dominio Auth-Access",
        landing_route="/dashboard",
        is_admin=False,
    )
    summary = summary.merge(SeedSummary(created_roles=1 if created else 0))

    created_permissions = 0
    created_role_permissions = 0
    for permission_code in BASE_PERMISSIONS:
        permission, permission_created = _upsert_permission(
            code=permission_code,
            description=f"Base permission: {permission_code}",
        )
        if permission_created:
            created_permissions += 1
        if _assign_permission_to_role(role=admin_role, permission=permission):
            created_role_permissions += 1

    summary = summary.merge(
        SeedSummary(
            created_permissions=created_permissions,
            created_role_permissions=created_role_permissions,
        )
    )

    admin_user, created_admin_user = _upsert_user(
        username="admin",
        email="tepexicuapandavid3@gmail.com",
        raw_password=admin_password,
        force_change_password=False,
    )
    created_user_roles = 0
    if _assign_role_to_user(user=admin_user, role=admin_role, is_primary=True):
        created_user_roles += 1

    base_user, created_base_user = _upsert_user(
        username="user_base",
        email="user@example.com",
        raw_password=admin_password,
        force_change_password=True,
    )
    if _assign_role_to_user(user=base_user, role=user_role, is_primary=True):
        created_user_roles += 1

    summary = summary.merge(
        SeedSummary(
            created_users=int(created_admin_user) + int(created_base_user),
            created_user_roles=created_user_roles,
        )
    )
    return summary


@transaction.atomic
def seed_auth_access_demo() -> SeedSummary:
    summary = SeedSummary()

    demo_roles = (
        ("support", "Soporte", "/dashboard", False),
        ("auditor", "Auditoria", "/admin/reportes", False),
        ("manager", "Manager", "/admin/usuarios", False),
    )
    role_map: dict[str, Roles] = {}
    created_roles = 0
    for role_name, role_description, landing_route, is_admin in demo_roles:
        role, created = _upsert_role(
            name=role_name,
            description=role_description,
            landing_route=landing_route,
            is_admin=is_admin,
        )
        role_map[role_name] = role
        created_roles += int(created)

    permission_defs = (
        ("read_audit", "Read audit logs"),
        ("read_profiles", "Read profile metadata"),
        ("manage_password_resets", "Manage password reset operations"),
    )

    permission_map: dict[str, Permisos] = {}
    created_permissions = 0
    for code, description in permission_defs:
        permission, created = _upsert_permission(code=code, description=description)
        permission_map[code] = permission
        created_permissions += int(created)

    role_permission_links = {
        "support": ("read_profiles", "manage_password_resets"),
        "auditor": ("read_audit", "read_profiles"),
        "manager": ("read_profiles",),
    }
    created_role_permissions = 0
    for role_name, permission_codes in role_permission_links.items():
        for code in permission_codes:
            if _assign_permission_to_role(
                role=role_map[role_name],
                permission=permission_map[code],
            ):
                created_role_permissions += 1

    demo_users = (
        ("demo_support", "demo.support@example.com", "support"),
        ("demo_auditor", "demo.auditor@example.com", "auditor"),
        ("demo_manager", "demo.manager@example.com", "manager"),
    )

    created_users = 0
    created_user_roles = 0
    for username, email, role_name in demo_users:
        user, user_created = _upsert_user(
            username=username,
            email=email,
            raw_password="AuthDemo_123456",
            force_change_password=False,
        )
        created_users += int(user_created)
        if _assign_role_to_user(user=user, role=role_map[role_name], is_primary=True):
            created_user_roles += 1

    summary = summary.merge(
        SeedSummary(
            created_users=created_users,
            created_roles=created_roles,
            created_permissions=created_permissions,
            created_role_permissions=created_role_permissions,
            created_user_roles=created_user_roles,
        )
    )
    return summary


@transaction.atomic
def seed_auth_access_edge_cases() -> SeedSummary:
    summary = SeedSummary()

    user_without_roles, user_created = _upsert_user(
        username="edge_no_role",
        email="edge.no.role@example.com",
        raw_password="EdgeCase_123456",
        force_change_password=False,
    )

    role_without_permissions, role_created = _upsert_role(
        name="edge_role_without_permissions",
        description="Role intentionally left without permissions",
        landing_route="/dashboard",
        is_admin=False,
    )

    orphan_permission, permission_created = _upsert_permission(
        code="edge_orphan_permission",
        description="Permission created but not linked to any role",
    )

    with_inactive_role, inactive_user_created = _upsert_user(
        username="edge_inactive_role_user",
        email="edge.inactive.role@example.com",
        raw_password="EdgeCase_123456",
        force_change_password=False,
    )

    created_user_roles = 0
    if _assign_role_to_user(
        user=with_inactive_role, role=role_without_permissions, is_primary=True
    ):
        created_user_roles += 1

    created_overrides = 0
    if _create_override(
        user=user_without_roles,
        permission=orphan_permission,
        efecto=RelUsuarioOverride.Efecto.DENY,
    ):
        created_overrides += 1

    summary = summary.merge(
        SeedSummary(
            created_users=int(user_created) + int(inactive_user_created),
            created_roles=int(role_created),
            created_permissions=int(permission_created),
            created_user_roles=created_user_roles,
            created_overrides=created_overrides,
        )
    )
    return summary


def ensure_base_permissions() -> Iterable[Permisos]:
    permissions: list[Permisos] = []
    for permission_code in BASE_PERMISSIONS:
        permission, _ = _upsert_permission(
            code=permission_code,
            description=f"Base permission: {permission_code}",
        )
        permissions.append(permission)
    return permissions


