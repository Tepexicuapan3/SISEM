"""API `parameters/` (parametros operativos por centro, reemplazo de ope_param).

Permisos:
  GET           -> admin:catalogos:parametros:read
  PUT / DELETE  -> admin:catalogos:parametros:update

Rutas:
  GET    parameters/                              lista con valores por centro
  GET    parameters/<key>/                        detalle
  PUT    parameters/<key>/                        {"value": ...} valor general
  PUT    parameters/<key>/centers/<center_id>/    {"value": ...} valor del centro
  DELETE parameters/<key>/centers/<center_id>/    vuelve al valor general
"""
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.audit_service import log_event

from .permissions import HasCatalogPermission
from .uses_case.parametro_use_case import ParametroError, ParametroUseCase as UseCase
from .views import ErrorMixin, _get_actor_id

PERMISSION_BASE = "admin:catalogos:parametros"


class ParametroValueSerializer(serializers.Serializer):
    # Texto: el tipo real lo valida el caso de uso contra la definicion.
    value = serializers.CharField(max_length=2000, allow_blank=True, trim_whitespace=True)


class _ParametroBaseView(ErrorMixin, APIView):
    def get_permissions(self):
        request = getattr(self, "request", None)
        read_only = request is not None and request.method in ("GET", "HEAD", "OPTIONS")
        return [HasCatalogPermission(action="read" if read_only else "update", catalog=PERMISSION_BASE)]

    @staticmethod
    def _audit_hook(request):
        def hook(action, resource_id, datos_antes, datos_despues):
            # raise_on_error=True: si la auditoria falla, se revierte el cambio.
            log_event(
                request,
                action,
                "SUCCESS",
                actor_user=request.user,
                resource_type="parametro",
                resource_id=resource_id,
                datos_antes=datos_antes,
                datos_despues=datos_despues,
                raise_on_error=True,
            )

        return hook

    def _run(self, request, call):
        try:
            return Response({"parameter": call()})
        except ParametroError as exc:
            return self._error(
                request, code=exc.code, message=exc.message,
                http_status=exc.http_status, details=exc.details,
            )

    def _value_or_error(self, request):
        serializer = ParametroValueSerializer(data=request.data)
        if not serializer.is_valid():
            return None, self._error(
                request, code="VALIDATION_ERROR", message="Datos de entrada inválidos",
                http_status=400, details=serializer.errors,
            )
        return serializer.validated_data["value"], None


class ParametroListView(_ParametroBaseView):
    def get(self, request):
        return Response({"items": UseCase.list_parameters()})


class ParametroDetailView(_ParametroBaseView):
    def get(self, request, key):
        return self._run(request, lambda: UseCase.get_parameter(key))

    def put(self, request, key):
        value, error = self._value_or_error(request)
        if error:
            return error
        return self._run(request, lambda: UseCase.update_general(
            key, value, actor_id=_get_actor_id(request.user), audit_hook=self._audit_hook(request),
        ))


class ParametroCentroView(_ParametroBaseView):
    def put(self, request, key, center_id):
        value, error = self._value_or_error(request)
        if error:
            return error
        return self._run(request, lambda: UseCase.set_center_value(
            key, center_id, value,
            actor_id=_get_actor_id(request.user), audit_hook=self._audit_hook(request),
        ))

    def delete(self, request, key, center_id):
        return self._run(request, lambda: UseCase.delete_center_value(
            key, center_id,
            actor_id=_get_actor_id(request.user), audit_hook=self._audit_hook(request),
        ))
