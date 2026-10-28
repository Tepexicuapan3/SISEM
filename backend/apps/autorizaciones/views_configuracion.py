"""API de configuracion del modulo de autorizaciones.

Permisos (atomicos, prefijo admin:autorizaciones-config):
  GET                      -> read
  PATCH / POST (mutaciones) -> update
CSRF y sesion los valida HasCatalogPermission (reutilizado de catalogos).
"""
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.audit_service import log_event
from apps.catalogos.permissions import HasCatalogPermission
from apps.catalogos.views import ErrorMixin, _get_actor_id

from .models import Modalidad, Motivo
from .repositories.configuracion_repository import ConfiguracionRepository as Repo
from .uses_case.configuracion_use_case import (
    ConfiguracionError,
    ConfiguracionUseCase as UseCase,
    motivo_a_dict,
    regla_a_dict,
    tipo_a_dict,
)

PERMISO_BASE = "admin:autorizaciones-config"


# ---------------------------------------------------------------------- #
# Entrada                                                                #
# ---------------------------------------------------------------------- #

class _Version(serializers.Serializer):
    version = serializers.IntegerField()


class TipoEdicionSerializer(_Version):
    modalidadPredeterminada = serializers.ChoiceField(choices=Modalidad.values, required=False)
    aprobacionesRequeridas = serializers.IntegerField(required=False)
    rechazoResuelveSolicitud = serializers.BooleanField(required=False)
    permiteRechazo = serializers.BooleanField(required=False)
    horasVigenciaSolicitud = serializers.IntegerField(required=False)
    horasEscalamiento = serializers.IntegerField(required=False)
    requiereCedula = serializers.BooleanField(required=False)


class _ReglaCampos(serializers.Serializer):
    modalidad = serializers.ChoiceField(choices=Modalidad.values, required=False, allow_null=True)
    aprobacionesRequeridas = serializers.IntegerField(required=False, allow_null=True)
    horasVigenciaSolicitud = serializers.IntegerField(required=False, allow_null=True)


class ReglaAltaSerializer(_ReglaCampos):
    tipoId = serializers.IntegerField()
    centroId = serializers.IntegerField()


class ReglaEdicionSerializer(_ReglaCampos, _Version):
    pass


class MotivoAltaSerializer(serializers.Serializer):
    ambito = serializers.ChoiceField(choices=Motivo.Ambito.values)
    clave = serializers.CharField(max_length=40)
    descripcion = serializers.CharField(max_length=150)
    requiereDescripcionLibre = serializers.BooleanField(required=False, default=False)


class MotivoEdicionSerializer(_Version):
    descripcion = serializers.CharField(max_length=150, required=False)
    requiereDescripcionLibre = serializers.BooleanField(required=False)
    activo = serializers.BooleanField(required=False)


# ---------------------------------------------------------------------- #
# Vistas                                                                 #
# ---------------------------------------------------------------------- #

class _BaseView(ErrorMixin, APIView):
    acciones = {"GET": "read", "POST": "update", "PATCH": "update"}

    def get_permissions(self):
        metodo = getattr(getattr(self, "request", None), "method", "GET")
        accion = self.acciones.get(metodo, "read" if metodo in ("HEAD", "OPTIONS") else None)
        return [HasCatalogPermission(action=accion or "__no_permitido__", catalog=PERMISO_BASE)]

    @staticmethod
    def _comun(request):
        def auditoria(accion, id_recurso, antes, despues):
            # raise_on_error=True: si la auditoria falla, se revierte la operacion.
            log_event(
                request, accion, "SUCCESS", actor_user=request.user,
                resource_type="autorizacion_configuracion", resource_id=id_recurso,
                datos_antes=antes, datos_despues=despues, raise_on_error=True,
            )

        return {"actor_id": _get_actor_id(request.user), "auditoria": auditoria}

    def _validar(self, request, clase, *, parcial=False):
        serializer = clase(data=request.data, partial=parcial)
        if serializer.is_valid():
            return {k: v for k, v in serializer.validated_data.items() if k in request.data or k == "version"}, None
        return None, self._error(
            request, code="VALIDATION_ERROR", message="Datos de entrada inválidos",
            http_status=status.HTTP_400_BAD_REQUEST, details=serializer.errors,
        )

    def _ejecutar(self, request, funcion, *args, http_status=status.HTTP_200_OK, clave, a_dict):
        try:
            registro = funcion(*args, **self._comun(request))
        except ConfiguracionError as exc:
            return self._error(
                request, code=exc.code, message=exc.message, http_status=exc.http_status, details=exc.details,
            )
        return Response({clave: a_dict(registro)}, status=http_status)


class TiposConfiguracionView(_BaseView):
    def get(self, request):
        return Response({"items": [tipo_a_dict(t) for t in Repo.tipos()]})


class TipoConfiguracionDetalleView(_BaseView):
    def patch(self, request, pk):
        datos, error = self._validar(request, TipoEdicionSerializer)
        if error:
            return error
        return self._ejecutar(request, UseCase.actualizar_tipo, pk, datos, clave="tipo", a_dict=tipo_a_dict)


class ReglasCentroView(_BaseView):
    def get(self, request):
        return Response({"items": [regla_a_dict(r) for r in Repo.reglas_vigentes()]})

    def post(self, request):
        datos, error = self._validar(request, ReglaAltaSerializer)
        if error:
            return error
        return self._ejecutar(
            request, UseCase.crear_regla, datos, http_status=status.HTTP_201_CREATED,
            clave="regla", a_dict=regla_a_dict,
        )


class ReglaCentroDetalleView(_BaseView):
    def patch(self, request, pk):
        datos, error = self._validar(request, ReglaEdicionSerializer)
        if error:
            return error
        return self._ejecutar(request, UseCase.actualizar_regla, pk, datos, clave="regla", a_dict=regla_a_dict)


class ReglaCentroBajaView(_BaseView):
    def post(self, request, pk):
        datos, error = self._validar(request, _Version)
        if error:
            return error
        return self._ejecutar(request, UseCase.dar_baja_regla, pk, datos, clave="regla", a_dict=regla_a_dict)


class MotivosConfiguracionView(_BaseView):
    def get(self, request):
        ambito = request.query_params.get("ambito") or None
        if ambito is not None and ambito not in Motivo.Ambito.values:
            return self._error(
                request, code="VALIDATION_ERROR", message="Parámetro ambito inválido",
                http_status=status.HTTP_400_BAD_REQUEST,
                details={"ambito": [f"Permitidos: {', '.join(Motivo.Ambito.values)}"]},
            )
        return Response({"items": [motivo_a_dict(m) for m in Repo.motivos(ambito)]})

    def post(self, request):
        datos, error = self._validar(request, MotivoAltaSerializer)
        if error:
            return error
        return self._ejecutar(
            request, UseCase.crear_motivo, datos, http_status=status.HTTP_201_CREATED,
            clave="motivo", a_dict=motivo_a_dict,
        )


class MotivoConfiguracionDetalleView(_BaseView):
    def patch(self, request, pk):
        datos, error = self._validar(request, MotivoEdicionSerializer)
        if error:
            return error
        return self._ejecutar(request, UseCase.actualizar_motivo, pk, datos, clave="motivo", a_dict=motivo_a_dict)
