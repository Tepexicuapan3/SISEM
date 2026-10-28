"""Lectura de las designaciones viejas (cat_designacion_autorizador) para la
migracion F8. Unico punto del modulo que lee tablas de catalogos: solo lee y
entrega datos planos, de modo que el resto del modulo no conoce esos modelos.
Se retira junto con la pantalla vieja (F9)."""
from dataclasses import dataclass
from datetime import date

from django.db.models import Prefetch

from apps.catalogos.models import DesignacionAlcance, DesignacionAutorizador

from ..models import AutorizadorTipo


@dataclass(frozen=True)
class DesignacionLegada:
    id_designacion: int
    id_usuario: int
    clave_tipo: str
    cargo: str
    numero_oficio: str | None
    fecha_inicio: date
    fecha_fin: date | None
    # [(tipo_alcance, id_centro, tipo_centro)], solo alcances activos.
    alcances: tuple


class DesignacionLegadaRepository:
    @staticmethod
    def activas() -> list[DesignacionLegada]:
        alcances_activos = DesignacionAlcance.objects.filter(is_active=True, deleted_at__isnull=True)
        designaciones = (
            DesignacionAutorizador.objects.filter(is_active=True, deleted_at__isnull=True)
            .select_related("authorization_type")
            .prefetch_related(Prefetch("scopes", queryset=alcances_activos.order_by("pk")))
            .order_by("user_id", "pk")
        )
        return [
            DesignacionLegada(
                id_designacion=d.id,
                id_usuario=d.user_id,
                clave_tipo=d.authorization_type.code,
                cargo=d.position,
                numero_oficio=d.official_letter,
                fecha_inicio=d.start_date,
                fecha_fin=d.end_date,
                alcances=tuple((a.scope_type, a.center_id, a.center_type) for a in d.scopes.all()),
            )
            for d in designaciones
        ]

    @staticmethod
    def ids_ya_migrados(ids_designacion) -> set[int]:
        return set(
            AutorizadorTipo.objects.filter(id_designacion_origen__in=list(ids_designacion))
            .values_list("id_designacion_origen", flat=True)
        )
