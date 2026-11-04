from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.administracion.services.rbac_resolver import RBACResolver
from apps.authentication.models import SyUsuario
from apps.authentication.services.auth_revision import serialize_auth_revision
from apps.authentication.services.centro_scope import alcance_contrato
from apps.authentication.services.authorization_service import (
    get_permission_context,
)


class UserRepository:
    # Acceso a datos para autenticacion

    @staticmethod
    def get_by_username(usuario):
        return (
            SyUsuario.objects.select_related("detalle").filter(usuario=usuario).first()
        )

    @staticmethod
    def get_by_email(correo):
        return SyUsuario.objects.select_related("detalle").filter(correo=correo).first()

    @staticmethod
    def get_by_id(user_id):
        return (
            SyUsuario.objects.select_related("detalle")
            .filter(id_usuario=user_id)
            .first()
        )

    @staticmethod
    def verify_password(user, raw_password):
        # Valida el hash de la clave.
        return check_password(raw_password, user.clave_hash)

    @staticmethod
    def update_password(user, raw_password):
        # Actualiza la clave usando hash seguro.
        user.clave_hash = make_password(raw_password)
        user.fch_modf = timezone.now()
        user.usr_modf = user
        user.save(update_fields=["clave_hash", "fch_modf", "usr_modf"])

    @staticmethod
    def mark_onboarding_completed(user):
        # Marca que el onboarding fue completado.
        user.cambiar_clave = False
        user.terminos_acept = True
        user.fch_terminos = timezone.now()
        user.fch_modf = timezone.now()
        user.usr_modf = user
        user.save(
            update_fields=[
                "cambiar_clave",
                "terminos_acept",
                "fch_terminos",
                "fch_modf",
                "usr_modf",
            ]
        )

    @staticmethod
    def mark_password_reset(user):
        # Marca el reset de password sin modificar terminos.
        user.cambiar_clave = False
        user.fch_modf = timezone.now()
        user.usr_modf = user
        user.save(update_fields=["cambiar_clave", "fch_modf", "usr_modf"])

    @staticmethod
    def reset_failed_attempts(user):
        # Reinicia estado de bloqueo.
        if user.est_bloqueado:
            user.est_bloqueado = False
            user.fch_modf = timezone.now()
            user.usr_modf = user
            user.save(update_fields=["est_bloqueado", "fch_modf", "usr_modf"])

    @staticmethod
    @transaction.atomic
    def mark_last_access(user, ip_address):
        # Registra ultimo acceso e IP.
        user.last_conexion = timezone.now()
        user.ip_ultima = ip_address
        user.fch_modf = timezone.now()
        user.usr_modf = user
        user.save(update_fields=["last_conexion", "ip_ultima", "fch_modf", "usr_modf"])

    @staticmethod
    def build_auth_user(user):
        # Mapea modelo a contrato AuthUser.
        profile = getattr(user, "detalle", None)
        roles, primary_role, landing_route, is_admin = _get_roles(user)
        permissions = _get_permissions(user, roles, is_admin)
        permission_context = get_permission_context(permissions)

        full_name = ""
        if profile and profile.nombre_completo:
            full_name = profile.nombre_completo
        else:
            full_name = " ".join(
                [
                    part
                    for part in [
                        profile.nombre if profile else "",
                        profile.paterno if profile else "",
                        profile.materno if profile else "",
                    ]
                    if part
                ]
            ).strip()

        return {
            "id": user.id_usuario,
            "username": user.usuario,
            "fullName": full_name,
            "email": user.correo,
            "primaryRole": primary_role,
            "landingRoute": landing_route,
            "roles": roles,
            "permissions": permissions,
            "effectivePermissions": permission_context["effectivePermissions"],
            "capabilities": permission_context["capabilities"],
            "permissionDependenciesVersion": permission_context[
                "permissionDependenciesVersion"
            ],
            "strictCapabilityPrefixes": permission_context["strictCapabilityPrefixes"],
            "authRevision": serialize_auth_revision(user),
            "mustChangePassword": user.cambiar_clave,
            "requiresOnboarding": user.cambiar_clave or not user.terminos_acept,
            "alcanceCentros": alcance_contrato(user, permissions),
        }


def _get_roles(user):
    # Use RBACResolver service from administracion domain
    role_objects, primary_role, landing_route, is_admin = RBACResolver.get_user_roles(
        user
    )

    # Extract role names as strings
    roles = [role.rol for role in role_objects]

    # Handle case where user has no roles
    if not primary_role and roles:
        primary_role = roles[0]
        # Try to get landing route from the role name
        role_obj = RBACResolver.get_role_by_name(primary_role)
        landing_route = role_obj.landing_route if role_obj else None
    elif not primary_role:
        primary_role = ""

    return roles, primary_role, landing_route, is_admin


def _get_permissions(user, roles, is_admin):
    # Use RBACResolver service from administracion domain
    return RBACResolver.get_effective_permissions(user)
