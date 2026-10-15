"""Serializers de `authorizer-designations/` (payload camelCase)."""
from datetime import date

from django.utils import timezone
from rest_framework import serializers

from .models import DesignacionAlcance

TIPOS_CENTRO = list(DesignacionAlcance.TIPOS_CENTRO_VALIDOS)


class AlcanceWriteSerializer(serializers.Serializer):
    centros = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    tiposCentro = serializers.ListField(
        child=serializers.ChoiceField(choices=TIPOS_CENTRO), required=False, default=list
    )
    # `global` es palabra reservada de Python: se declara en el namespace de la clase.
    locals()["global"] = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        has_items = bool(attrs.get("centros")) or bool(attrs.get("tiposCentro"))
        is_global = bool(attrs.get("global"))
        if not has_items and not is_global:
            raise serializers.ValidationError(
                "El alcance debe incluir al menos un centro, un tipo de centro o GLOBAL explicito"
            )
        if is_global and has_items:
            raise serializers.ValidationError(
                "GLOBAL no se combina con centros o tipos de centro: ya los cubre"
            )
        return attrs


class DesignacionWriteSerializer(serializers.Serializer):
    userId = serializers.IntegerField(min_value=1)
    tipoAutorizacionId = serializers.IntegerField(min_value=1)
    cargo = serializers.CharField(max_length=60)
    fechaInicio = serializers.DateField()
    fechaFin = serializers.DateField(required=False, allow_null=True, default=None)
    oficio = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True, default=None
    )
    imgFirma = serializers.CharField(max_length=200, required=False, allow_null=True, allow_blank=True)
    alcance = AlcanceWriteSerializer()

    def validate_cargo(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El cargo es obligatorio")
        return value

    def validate_oficio(self, value):
        return (value or "").strip() or None

    def validate(self, attrs):
        start, end = attrs["fechaInicio"], attrs.get("fechaFin")
        if end is not None and end < start:
            raise serializers.ValidationError(
                {"fechaFin": ["La fecha de fin no puede ser anterior a la de inicio"]}
            )
        if "imgFirma" in attrs:
            attrs["imgFirma"] = (attrs["imgFirma"] or "").strip() or None
        return attrs


def _is_current(designation, today: date) -> bool:
    if not designation.is_active or designation.deleted_at is not None:
        return False
    if designation.start_date > today:
        return False
    return designation.end_date is None or designation.end_date >= today


def build_designation_payload(designation, scopes, user_name: str | None = None) -> dict:
    """Representacion de lectura. `scopes`: items de alcance ACTIVOS de la designacion."""
    today = timezone.localdate()
    centers = [
        {"id": s.center_id, "name": s.center.name if getattr(s, "center", None) else ""}
        for s in scopes
        if s.scope_type == DesignacionAlcance.Alcance.CENTRO
    ]
    user = designation.user
    return {
        "id": designation.id,
        "userId": designation.user_id,
        "user": {
            "id": designation.user_id,
            "username": user.usuario,
            "name": user_name or user.usuario,
        },
        "tipoAutorizacionId": designation.authorization_type_id,
        "tipoAutorizacion": {
            "id": designation.authorization_type_id,
            "name": designation.authorization_type.name,
            "code": designation.authorization_type.code,
        },
        "cargo": designation.position,
        "fechaInicio": designation.start_date.isoformat(),
        "fechaFin": designation.end_date.isoformat() if designation.end_date else None,
        "oficio": designation.official_letter,
        "imgFirma": designation.signature_image,
        "alcance": {
            "centros": centers,
            "tiposCentro": sorted(
                s.center_type
                for s in scopes
                if s.scope_type == DesignacionAlcance.Alcance.TIPO_CENTRO
            ),
            "global": any(s.scope_type == DesignacionAlcance.Alcance.GLOBAL for s in scopes),
        },
        "isActive": designation.is_active,
        "vigente": _is_current(designation, today),
        "createdAt": designation.created_at.isoformat() if designation.created_at else None,
    }
