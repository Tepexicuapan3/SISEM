"""Consulta y edicion de parametros operativos (reemplazo de ope_param).

Reglas:
  - El valor se valida contra el tipo y los limites de la definicion; se
    guarda en forma canonica.
  - Solo las definiciones con ``allows_center_override`` aceptan valor por
    centro; el centro debe existir y estar activo.
  - No se crean ni borran definiciones desde la API: las agrega el codigo que
    las consume (migracion de datos).
  - Toda mutacion corre en una transaccion junto con su evento de auditoria
    (``audit_hook(action, resource_id, antes, despues)``); si la auditoria
    falla, se revierte. La cache se invalida despues del commit.
"""
from __future__ import annotations

from typing import Callable

from django.db import transaction

from ..models import CatCentroAtencion, ParametroCentro, ParametroDefinicion
from ..services import parametro_service

AuditHook = Callable[..., None]


class ParametroError(Exception):
    """Error de negocio con contrato HTTP (code, message, status, details)."""

    def __init__(self, code: str, message: str, http_status: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _definition_payload(definition, center_values):
    return {
        "key": definition.key,
        "description": definition.description,
        "module": definition.module,
        "valueType": definition.value_type,
        "generalValue": definition.general_value,
        "minValue": float(definition.min_value) if definition.min_value is not None else None,
        "maxValue": float(definition.max_value) if definition.max_value is not None else None,
        "allowsCenterOverride": definition.allows_center_override,
        "legacySource": definition.legacy_source,
        "updatedAt": definition.updated_at,
        "centerValues": [
            {
                "centerId": cv.center_id,
                "centerName": cv.center.name,
                "value": cv.value,
                "updatedAt": cv.updated_at,
            }
            for cv in center_values
        ],
    }


def _get_definition_or_404(key, *, for_update=False):
    qs = ParametroDefinicion.objects.filter(key=key, is_active=True)
    if for_update:
        qs = qs.select_for_update()
    definition = qs.first()
    if definition is None:
        raise ParametroError("PARAMETER_NOT_FOUND", "Parámetro no encontrado.", 404)
    return definition


def _normalize_or_400(definition, raw):
    try:
        return parametro_service.normalize_value(definition, raw)
    except parametro_service.ParametroValueError as exc:
        raise ParametroError(
            "VALIDATION_ERROR", "Datos de entrada inválidos", 400, details={"value": [str(exc)]},
        ) from exc


def _ensure_center_override_allowed(definition):
    if not definition.allows_center_override:
        raise ParametroError(
            "CENTER_OVERRIDE_NOT_ALLOWED",
            "Este parámetro es general: no admite valor por centro.",
            409,
        )


class ParametroUseCase:
    @staticmethod
    def list_parameters():
        definitions = list(ParametroDefinicion.objects.filter(is_active=True).order_by("module", "key"))
        by_definition = {d.id: [] for d in definitions}
        for cv in (
            ParametroCentro.objects.filter(definition_id__in=by_definition)
            .select_related("center")
            .order_by("center__name")
        ):
            by_definition[cv.definition_id].append(cv)
        return [_definition_payload(d, by_definition[d.id]) for d in definitions]

    @staticmethod
    def get_parameter(key):
        definition = _get_definition_or_404(key)
        values = definition.center_values.select_related("center").order_by("center__name")
        return _definition_payload(definition, list(values))

    @staticmethod
    def update_general(key, value, *, actor_id, audit_hook: AuditHook):
        with transaction.atomic():
            definition = _get_definition_or_404(key, for_update=True)
            normalized = _normalize_or_400(definition, value)
            before = {"key": key, "generalValue": definition.general_value}
            definition.general_value = normalized
            definition.updated_by_id = actor_id
            definition.save(update_fields=["general_value", "updated_by_id", "updated_at"])
            audit_hook("ParameterGeneralUpdated", definition.id, before, {"key": key, "generalValue": normalized})
            parametro_service.invalidate(key)
        return ParametroUseCase.get_parameter(key)

    @staticmethod
    def set_center_value(key, center_id, value, *, actor_id, audit_hook: AuditHook):
        with transaction.atomic():
            definition = _get_definition_or_404(key, for_update=True)
            _ensure_center_override_allowed(definition)
            if not CatCentroAtencion.objects.filter(pk=center_id, is_active=True).exists():
                raise ParametroError("CENTER_NOT_FOUND", "Centro de atención no encontrado.", 404)
            normalized = _normalize_or_400(definition, value)
            current = ParametroCentro.objects.filter(definition=definition, center_id=center_id).first()
            before = {"key": key, "centerId": center_id, "value": current.value if current else None}
            if current is None:
                ParametroCentro.objects.create(
                    definition=definition, center_id=center_id, value=normalized,
                    created_by_id=actor_id, updated_by_id=actor_id,
                )
            else:
                current.value = normalized
                current.updated_by_id = actor_id
                current.save(update_fields=["value", "updated_by_id", "updated_at"])
            audit_hook(
                "ParameterCenterValueSet", definition.id, before,
                {"key": key, "centerId": center_id, "value": normalized},
            )
            parametro_service.invalidate(key)
        return ParametroUseCase.get_parameter(key)

    @staticmethod
    def delete_center_value(key, center_id, *, actor_id, audit_hook: AuditHook):
        with transaction.atomic():
            definition = _get_definition_or_404(key, for_update=True)
            current = ParametroCentro.objects.filter(definition=definition, center_id=center_id).first()
            if current is None:
                raise ParametroError(
                    "CENTER_VALUE_NOT_FOUND", "El centro no tiene un valor propio para este parámetro.", 404,
                )
            before = {"key": key, "centerId": center_id, "value": current.value}
            current.delete()
            audit_hook(
                "ParameterCenterValueDeleted", definition.id, before,
                {"key": key, "centerId": center_id, "value": None, "deletedBy": actor_id},
            )
            parametro_service.invalidate(key)
        return ParametroUseCase.get_parameter(key)
