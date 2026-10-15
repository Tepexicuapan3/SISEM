"""API `authorizer-designations/` (designacion de autorizadores).

Permisos (NO pasan por el mixin generico de catalogos, que arma
`admin:catalogos:<x>:<accion>`):
  GET                      -> admin:autorizadores:designacion:read
  POST / PUT / DELETE      -> admin:autorizadores:designacion:write
  alcance GLOBAL (crear o tocar una designacion global)
                           -> ademas admin:autorizadores:designacion:global
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.audit_service import log_event

from .designacion_serializers import DesignacionWriteSerializer, build_designation_payload
from .models import DesignacionAlcance
from .permissions import HasCatalogPermission
from .repositories.designacion_autorizador_repository import (
    DesignacionAutorizadorRepository as Repo,
)
from .serializers import build_user_ref
from .uses_case.designacion_autorizador_use_case import (
    DesignacionAutorizadorUseCase as UseCase,
    DesignacionError,
)
from .views import (
    ErrorMixin,
    PaginationMixin,
    _PaginationError,
    _get_actor_id,
    _parse_bool_param,
)

PERMISSION_BASE = "admin:autorizadores:designacion"
PERMISSION_GLOBAL = f"{PERMISSION_BASE}:global"


class _DesignacionBaseView(ErrorMixin, APIView):
    def get_permissions(self):
        request = getattr(self, "request", None)
        read_only = request is not None and request.method in ("GET", "HEAD", "OPTIONS")
        return [HasCatalogPermission(action="read" if read_only else "write", catalog=PERMISSION_BASE)]

    @staticmethod
    def _can_grant_global(request) -> bool:
        permissions = UserRepository.build_auth_user(request.user).get("permissions", [])
        return "*" in permissions or PERMISSION_GLOBAL in permissions

    @staticmethod
    def _audit_hook(request):
        def hook(action, resource_id, datos_antes, datos_despues):
            # raise_on_error=True: si la auditoria falla, se revierte la mutacion.
            log_event(
                request,
                action,
                "SUCCESS",
                actor_user=request.user,
                resource_type="designacion_autorizador",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                raise_on_error=True,
            )

        return hook

    def _domain_error(self, request, exc: DesignacionError):
        return self._error(
            request,
            code=exc.code,
            message=exc.message,
            http_status=exc.http_status,
            details=exc.details,
        )

    def _validation_error(self, request, serializer):
        return self._error(
            request,
            code="VALIDATION_ERROR",
            message="Datos de entrada inválidos",
            http_status=status.HTTP_400_BAD_REQUEST,
            details=serializer.errors,
        )

    @staticmethod
    def _serialize_many(designations):
        ids = [d.id for d in designations]
        scopes_by_designation: dict[int, list] = {i: [] for i in ids}
        for scope in (
            DesignacionAlcance.objects.filter(
                designation_id__in=ids, is_active=True, deleted_at__isnull=True
            )
            .select_related("center")
            .order_by("id")
        ):
            scopes_by_designation[scope.designation_id].append(scope)
        return [
            build_designation_payload(
                d,
                scopes_by_designation[d.id],
                user_name=(build_user_ref(d.user_id) or {}).get("name"),
            )
            for d in designations
        ]

    def _detail_response(self, designation, *, http_status=status.HTTP_200_OK):
        fresh = Repo.get_by_id(designation.id)
        return Response({"designation": self._serialize_many([fresh])[0]}, status=http_status)


class DesignacionListCreateView(PaginationMixin, _DesignacionBaseView):
    SORT_MAP = {
        "createdAt": "created_at",
        "cargo": "position",
        "fechaInicio": "start_date",
        "fechaFin": "end_date",
        "isActive": "is_active",
    }

    def get(self, request):
        try:
            page, page_size = self._parse_pagination(request)
        except _PaginationError as exc:
            return exc.response

        params = request.query_params
        sort_by = params.get("sortBy", "createdAt")
        sort_order = params.get("sortOrder", "desc")
        if sort_by not in self.SORT_MAP:
            return self._error(
                request,
                code="VALIDATION_ERROR",
                message="Parámetro sortBy inválido",
                http_status=status.HTTP_400_BAD_REQUEST,
                details={"sortBy": [f"Permitidos: {', '.join(self.SORT_MAP)}"]},
            )
        if sort_order not in ("asc", "desc"):
            return self._error(
                request,
                code="VALIDATION_ERROR",
                message="Parámetro sortOrder inválido",
                http_status=status.HTTP_400_BAD_REQUEST,
                details={"sortOrder": ["Debe ser 'asc' o 'desc'"]},
            )

        qs = Repo.base_queryset().filter(deleted_at__isnull=True)

        if search := params.get("search"):
            qs = qs.filter(Q(user__usuario__icontains=search) | Q(position__icontains=search))

        if type_id := params.get("tipoAutorizacionId"):
            if not type_id.isdigit():
                return self._error(
                    request,
                    code="VALIDATION_ERROR",
                    message="Parámetro tipoAutorizacionId inválido",
                    http_status=status.HTTP_400_BAD_REQUEST,
                    details={"tipoAutorizacionId": ["Debe ser un entero"]},
                )
            qs = qs.filter(authorization_type_id=int(type_id))

        if (raw_active := params.get("isActive")) is not None:
            is_active = _parse_bool_param(raw_active)
            if is_active is None:
                return self._error(
                    request,
                    code="VALIDATION_ERROR",
                    message="Parámetro isActive inválido",
                    http_status=status.HTTP_400_BAD_REQUEST,
                    details={"isActive": ["Debe ser 'true' o 'false'"]},
                )
            qs = qs.filter(is_active=is_active)

        order_field = self.SORT_MAP[sort_by]
        qs = qs.order_by(f"-{order_field}" if sort_order == "desc" else order_field, "-id")

        items, total, total_pages = self._paginate_queryset(qs, page, page_size)
        return self._paginated_response(
            self._serialize_many(list(items)), page, page_size, total, total_pages
        )

    def post(self, request):
        serializer = DesignacionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_error(request, serializer)

        try:
            designation = UseCase.create(
                serializer.validated_data,
                actor_id=_get_actor_id(request.user),
                can_grant_global=self._can_grant_global(request),
                audit_hook=self._audit_hook(request),
            )
        except DesignacionError as exc:
            return self._domain_error(request, exc)
        return self._detail_response(designation, http_status=status.HTTP_201_CREATED)


class DesignacionDetailView(_DesignacionBaseView):
    def get(self, request, pk):
        designation = Repo.get_by_id(pk)
        if designation is None or designation.deleted_at is not None:
            return self._not_found(request)
        return self._detail_response(designation)

    def put(self, request, pk):
        serializer = DesignacionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_error(request, serializer)

        try:
            designation = UseCase.update(
                pk,
                serializer.validated_data,
                actor_id=_get_actor_id(request.user),
                can_grant_global=self._can_grant_global(request),
                audit_hook=self._audit_hook(request),
            )
        except DesignacionError as exc:
            return self._domain_error(request, exc)
        return self._detail_response(designation)

    def delete(self, request, pk):
        try:
            UseCase.revoke(
                pk,
                actor_id=_get_actor_id(request.user),
                audit_hook=self._audit_hook(request),
            )
        except DesignacionError as exc:
            return self._domain_error(request, exc)
        return Response({"success": True})

    def _not_found(self, request):
        return self._error(
            request,
            code="DESIGNATION_NOT_FOUND",
            message="Designacion no encontrada",
            http_status=status.HTTP_404_NOT_FOUND,
        )
