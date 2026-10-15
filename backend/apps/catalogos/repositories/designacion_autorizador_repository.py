from datetime import date

from django.db.models import Q, QuerySet
from django.utils import timezone

from ..models import (
    CatCentroAtencion,
    DesignacionAlcance,
    DesignacionAutorizador,
)

SCOPE_PRIORITY = {
    DesignacionAlcance.Alcance.CENTRO: 0,
    DesignacionAlcance.Alcance.TIPO_CENTRO: 1,
    DesignacionAlcance.Alcance.GLOBAL: 2,
}


class DesignacionAutorizadorRepository:
    """Acceso a datos de designaciones. Sin reglas de negocio (ver
    `designacion_autorizador_service`) y sin ORM sobre JSONField."""

    # ------------------------------------------------------------------ #
    # Consulta para la politica puede_autorizar                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_center_type(center_id: int) -> str | None:
        return (
            CatCentroAtencion.objects.filter(pk=center_id)
            .values_list("center_type", flat=True)
            .first()
        )

    @staticmethod
    def find_covering_scopes(
        *,
        user_id: int,
        type_code: str,
        center_id: int,
        center_type: str | None,
        on_date: date,
    ) -> list[dict]:
        """Items de alcance VIGENTES que cubren (centro, fecha) para el usuario y tipo.

        Reglas aplicadas en SQL:
          - designacion y alcance activos y no dados de baja;
          - fe_inicio <= fecha <= fe_fin (limites inclusivos; fe_fin NULL = sin fin);
          - CENTRO por id, TIPO_CENTRO por el tipo ACTUAL del centro (cubre centros
            dados de alta despues), GLOBAL solo si la designacion tiene fe_fin.
        La adscripcion del usuario NO se consulta.
        Devuelve dicts ordenados por especificidad (CENTRO, TIPO_CENTRO, GLOBAL).
        """
        coverage = Q(scope_type=DesignacionAlcance.Alcance.CENTRO, center_id=center_id)
        if center_type:
            coverage |= Q(
                scope_type=DesignacionAlcance.Alcance.TIPO_CENTRO,
                center_type=center_type,
            )
        coverage |= Q(
            scope_type=DesignacionAlcance.Alcance.GLOBAL,
            designation__end_date__isnull=False,
        )

        rows = list(
            DesignacionAlcance.objects.filter(
                coverage,
                is_active=True,
                deleted_at__isnull=True,
                designation__is_active=True,
                designation__deleted_at__isnull=True,
                designation__user_id=user_id,
                designation__authorization_type__code=type_code,
                designation__start_date__lte=on_date,
            )
            .filter(
                Q(designation__end_date__isnull=True) | Q(designation__end_date__gte=on_date)
            )
            .values("id", "scope_type", "designation_id")
        )
        rows.sort(key=lambda r: (SCOPE_PRIORITY[r["scope_type"]], r["id"]))
        return rows

    # ------------------------------------------------------------------ #
    # CRUD de designaciones                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def base_queryset() -> QuerySet[DesignacionAutorizador]:
        return DesignacionAutorizador.objects.select_related("user", "authorization_type")

    @staticmethod
    def get_by_id(designation_id: int) -> DesignacionAutorizador | None:
        return (
            DesignacionAutorizadorRepository.base_queryset()
            .filter(pk=designation_id)
            .first()
        )

    @staticmethod
    def get_for_update(designation_id: int) -> DesignacionAutorizador | None:
        return (
            DesignacionAutorizador.objects.select_for_update()
            .filter(pk=designation_id)
            .first()
        )

    @staticmethod
    def active_scopes(designation_id: int) -> list[DesignacionAlcance]:
        return list(
            DesignacionAlcance.objects.filter(
                designation_id=designation_id,
                is_active=True,
                deleted_at__isnull=True,
            )
            .select_related("center")
            .order_by("id")
        )

    @staticmethod
    def exists_active_for(user_id: int, type_id: int, exclude_id: int | None = None) -> bool:
        qs = DesignacionAutorizador.objects.filter(
            user_id=user_id,
            authorization_type_id=type_id,
            is_active=True,
            deleted_at__isnull=True,
        )
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        return qs.exists()

    @staticmethod
    def create(**fields) -> DesignacionAutorizador:
        return DesignacionAutorizador.objects.create(**fields)

    @staticmethod
    def add_scope(designation, *, scope_type, center_id=None, center_type=None, actor_id=None):
        return DesignacionAlcance.objects.create(
            designation=designation,
            scope_type=scope_type,
            center_id=center_id,
            center_type=center_type,
            created_by_id=actor_id,
        )

    @staticmethod
    def soft_delete_scopes(scope_ids: list[int], actor_id: int | None) -> None:
        if not scope_ids:
            return
        DesignacionAlcance.objects.filter(pk__in=scope_ids).update(
            is_active=False,
            deleted_at=timezone.now(),
            deleted_by_id=actor_id,
        )

    @staticmethod
    def soft_delete(designation: DesignacionAutorizador, actor_id: int | None) -> None:
        designation.is_active = False
        designation.deleted_at = timezone.now()
        designation.deleted_by_id = actor_id
        designation.save(update_fields=["is_active", "deleted_at", "deleted_by_id"])
        DesignacionAutorizadorRepository.soft_delete_scopes(
            list(
                DesignacionAlcance.objects.filter(
                    designation=designation, deleted_at__isnull=True
                ).values_list("pk", flat=True)
            ),
            actor_id,
        )
