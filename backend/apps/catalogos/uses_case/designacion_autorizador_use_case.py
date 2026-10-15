"""Alta / edicion / baja de designaciones de autorizadores.

Reglas (spec D1 del change cancelacion-nota-cascada):
  - R1.1  >=1 item de alcance; cada item es CENTRO | TIPO_CENTRO | GLOBAL
          explicito (la BD ademas lo garantiza con CheckConstraint).
  - R1.3  GLOBAL exige fe_fin y el permiso `admin:autorizadores:designacion:global`
          (el permiso se resuelve en la vista y llega como `can_grant_global`).
          Se valida PRIMERO el permiso (403) y despues la fe_fin (400), para que
          un admin sin permiso nunca obtenga informacion ni guarde nada.
  - R1.4  La adscripcion del usuario nunca se modifica ni se consulta.
  - Una sola designacion activa por (usuario, tipo); el alcance se edita con
    baja logica de items + alta de nuevos (nunca DELETE fisico).
Toda mutacion corre en una transaccion junto con su evento de auditoria
(`audit_hook(action, resource_id, antes, despues)`); si la auditoria falla, se
revierte todo.
"""
from __future__ import annotations

from typing import Callable

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.authentication.models import SyUsuario

from ..models import CatCentroAtencion, DesignacionAlcance, DesignacionAutorizador, TpAutorizacion
from ..repositories.designacion_autorizador_repository import (
    DesignacionAutorizadorRepository as Repo,
)

AuditHook = Callable[..., None]


class DesignacionError(Exception):
    """Error de negocio con contrato HTTP (code, message, status, details)."""

    def __init__(self, code: str, message: str, http_status: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _scope_key(scope_type: str, center_id, center_type) -> tuple:
    return (scope_type, center_id, center_type)


def _desired_scope_keys(alcance: dict) -> list[tuple]:
    keys: list[tuple] = []
    if alcance.get("global"):
        keys.append(_scope_key(DesignacionAlcance.Alcance.GLOBAL, None, None))
    for center_id in dict.fromkeys(alcance.get("centros") or []):
        keys.append(_scope_key(DesignacionAlcance.Alcance.CENTRO, center_id, None))
    for tipo in dict.fromkeys(alcance.get("tiposCentro") or []):
        keys.append(_scope_key(DesignacionAlcance.Alcance.TIPO_CENTRO, None, tipo))
    return keys


def snapshot(designation: DesignacionAutorizador, scopes: list[DesignacionAlcance]) -> dict:
    """Estado serializable (para auditoria). Sin passwords ni datos sensibles."""
    return {
        "id": designation.id,
        "userId": designation.user_id,
        "tipoAutorizacionId": designation.authorization_type_id,
        "cargo": designation.position,
        "fechaInicio": designation.start_date.isoformat() if designation.start_date else None,
        "fechaFin": designation.end_date.isoformat() if designation.end_date else None,
        "oficio": designation.official_letter,
        "alcance": {
            "centros": sorted(s.center_id for s in scopes if s.scope_type == "CENTRO"),
            "tiposCentro": sorted(s.center_type for s in scopes if s.scope_type == "TIPO_CENTRO"),
            "global": any(s.scope_type == "GLOBAL" for s in scopes),
        },
    }


class DesignacionAutorizadorUseCase:

    # ------------------------------------------------------------------ #
    # Validaciones                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_global_rules(data: dict, can_grant_global: bool) -> None:
        if data["alcance"].get("global"):
            if not can_grant_global:
                raise DesignacionError(
                    "GLOBAL_PERMISSION_REQUIRED",
                    "No tienes permiso para otorgar alcance GLOBAL",
                    403,
                )
            if not data.get("fechaFin"):
                raise DesignacionError(
                    "GLOBAL_REQUIRES_END_DATE",
                    "El alcance GLOBAL exige fecha de fin de vigencia",
                    400,
                    {"fechaFin": ["Obligatoria con alcance GLOBAL"]},
                )

    @staticmethod
    def _validate_references(data: dict) -> None:
        errors: dict[str, list[str]] = {}

        user = SyUsuario.objects.filter(pk=data["userId"]).only("est_activo").first()
        if user is None:
            errors["userId"] = ["Usuario no encontrado"]
        elif not user.est_activo:
            errors["userId"] = ["El usuario esta inactivo"]

        if not TpAutorizacion.objects.filter(pk=data["tipoAutorizacionId"], is_active=True).exists():
            errors["tipoAutorizacionId"] = ["Tipo de autorizacion no encontrado o inactivo"]

        center_ids = list(dict.fromkeys(data["alcance"].get("centros") or []))
        if center_ids:
            found = set(
                CatCentroAtencion.objects.filter(pk__in=center_ids).values_list("pk", flat=True)
            )
            missing = [cid for cid in center_ids if cid not in found]
            if missing:
                errors["alcance"] = [f"Centros no encontrados: {missing}"]

        if errors:
            raise DesignacionError("VALIDATION_ERROR", "Datos de entrada inválidos", 400, errors)

    @staticmethod
    def _duplicate_error() -> DesignacionError:
        return DesignacionError(
            "DESIGNATION_EXISTS",
            "El usuario ya tiene una designacion activa de ese tipo de autorizacion",
            409,
        )

    # ------------------------------------------------------------------ #
    # Casos de uso                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create(
        data: dict,
        *,
        actor_id: int | None,
        can_grant_global: bool,
        audit_hook: AuditHook | None = None,
    ) -> DesignacionAutorizador:
        DesignacionAutorizadorUseCase._validate_global_rules(data, can_grant_global)
        DesignacionAutorizadorUseCase._validate_references(data)

        if Repo.exists_active_for(data["userId"], data["tipoAutorizacionId"]):
            raise DesignacionAutorizadorUseCase._duplicate_error()

        try:
            with transaction.atomic():
                designation = Repo.create(
                    user_id=data["userId"],
                    authorization_type_id=data["tipoAutorizacionId"],
                    position=data["cargo"],
                    start_date=data["fechaInicio"],
                    end_date=data.get("fechaFin"),
                    official_letter=data.get("oficio"),
                    signature_image=data.get("imgFirma"),
                    created_by_id=actor_id,
                )
                for scope_type, center_id, center_type in _desired_scope_keys(data["alcance"]):
                    Repo.add_scope(
                        designation,
                        scope_type=scope_type,
                        center_id=center_id,
                        center_type=center_type,
                        actor_id=actor_id,
                    )
                if audit_hook:
                    audit_hook(
                        "AuthorizerDesignationCreated",
                        designation.id,
                        None,
                        snapshot(designation, Repo.active_scopes(designation.id)),
                    )
        except IntegrityError as exc:  # carrera con otra alta del mismo (usuario, tipo)
            raise DesignacionAutorizadorUseCase._duplicate_error() from exc
        return designation

    @staticmethod
    def update(
        designation_id: int,
        data: dict,
        *,
        actor_id: int | None,
        can_grant_global: bool,
        audit_hook: AuditHook | None = None,
    ) -> DesignacionAutorizador:
        try:
            with transaction.atomic():
                designation = Repo.get_for_update(designation_id)
                if designation is None or designation.deleted_at is not None:
                    raise DesignacionError(
                        "DESIGNATION_NOT_FOUND", "Designacion no encontrada", 404
                    )

                current_scopes = Repo.active_scopes(designation.id)
                had_global = any(s.scope_type == "GLOBAL" for s in current_scopes)
                # Editar una designacion que ya es GLOBAL tambien exige el permiso:
                # si no, cualquier admin podria alargarle la vigencia.
                if had_global and not can_grant_global:
                    raise DesignacionError(
                        "GLOBAL_PERMISSION_REQUIRED",
                        "No tienes permiso para modificar una designacion con alcance GLOBAL",
                        403,
                    )
                DesignacionAutorizadorUseCase._validate_global_rules(data, can_grant_global)
                DesignacionAutorizadorUseCase._validate_references(data)

                if Repo.exists_active_for(
                    data["userId"], data["tipoAutorizacionId"], exclude_id=designation.id
                ):
                    raise DesignacionAutorizadorUseCase._duplicate_error()

                before = snapshot(designation, current_scopes)

                designation.user_id = data["userId"]
                designation.authorization_type_id = data["tipoAutorizacionId"]
                designation.position = data["cargo"]
                designation.start_date = data["fechaInicio"]
                designation.end_date = data.get("fechaFin")
                designation.official_letter = data.get("oficio")
                if "imgFirma" in data:
                    designation.signature_image = data["imgFirma"]
                designation.updated_at = timezone.now()
                designation.updated_by_id = actor_id
                designation.save()

                # Diff de alcance: baja logica de lo que sobra, alta de lo que falta.
                desired = _desired_scope_keys(data["alcance"])
                desired_set = set(desired)
                existing_by_key = {
                    _scope_key(s.scope_type, s.center_id, s.center_type): s for s in current_scopes
                }
                Repo.soft_delete_scopes(
                    [s.id for key, s in existing_by_key.items() if key not in desired_set],
                    actor_id,
                )
                for scope_type, center_id, center_type in desired:
                    if (scope_type, center_id, center_type) in existing_by_key:
                        continue
                    Repo.add_scope(
                        designation,
                        scope_type=scope_type,
                        center_id=center_id,
                        center_type=center_type,
                        actor_id=actor_id,
                    )

                if audit_hook:
                    audit_hook(
                        "AuthorizerDesignationUpdated",
                        designation.id,
                        before,
                        snapshot(designation, Repo.active_scopes(designation.id)),
                    )
        except IntegrityError as exc:
            raise DesignacionAutorizadorUseCase._duplicate_error() from exc
        return designation

    @staticmethod
    def revoke(
        designation_id: int,
        *,
        actor_id: int | None,
        audit_hook: AuditHook | None = None,
    ) -> None:
        with transaction.atomic():
            designation = Repo.get_for_update(designation_id)
            if designation is None or designation.deleted_at is not None:
                raise DesignacionError("DESIGNATION_NOT_FOUND", "Designacion no encontrada", 404)
            before = snapshot(designation, Repo.active_scopes(designation.id))
            Repo.soft_delete(designation, actor_id)
            if audit_hook:
                audit_hook("AuthorizerDesignationRevoked", designation.id, before, None)
