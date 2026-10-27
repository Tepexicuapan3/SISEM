"""API de administracion de autorizadores medicos.

Permisos (atomicos, prefijo admin:autorizadores):
  GET (listado, detalle, historial, usuarios elegibles, catalogos) -> read
  POST alta                                                         -> create
  PATCH edicion de tipos/centros, POST renovar                      -> update
  POST suspender / reactivar / baja                                 -> status
  otorgar o tocar alcance GLOBAL                                    -> ademas global

CSRF y sesion los valida HasCatalogPermission (reutilizado de catalogos).
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.audit_service import log_event
from apps.catalogos.permissions import HasCatalogPermission
from apps.catalogos.views import ErrorMixin, PaginationMixin, _PaginationError, _get_actor_id

from .domain.vigencia import EstadoVigencia
from .models import Autorizador, Motivo, TipoAutorizacion
from .repositories.autorizador_repository import AutorizadorRepository as Repo
from .serializers import (
    AutorizadorAltaSerializer,
    AutorizadorEdicionSerializer,
    CambioEstatusSerializer,
    RenovacionSerializer,
    VersionSerializer,
    construir_autorizadores,
    construir_movimiento,
    construir_usuario_elegible,
)
from .uses_case.autorizador_use_case import AutorizadorError, AutorizadorUseCase as UseCase

PERMISO_BASE = "admin:autorizadores"
PERMISO_GLOBAL = f"{PERMISO_BASE}:global"


class _BaseView(ErrorMixin, APIView):
    # {metodo HTTP: accion del permiso}
    acciones = {"GET": "read"}

    def get_permissions(self):
        metodo = getattr(getattr(self, "request", None), "method", "GET")
        accion = self.acciones.get(metodo, "read" if metodo in ("HEAD", "OPTIONS") else None)
        return [HasCatalogPermission(action=accion or "__no_permitido__", catalog=PERMISO_BASE)]

    @staticmethod
    def _puede_otorgar_global(request) -> bool:
        permisos = UserRepository.build_auth_user(request.user).get("permissions", [])
        return "*" in permisos or PERMISO_GLOBAL in permisos

    @staticmethod
    def _identificador_peticion(request):
        return request.headers.get("X-Request-ID")

    @staticmethod
    def _auditoria(request):
        def registrar(accion, id_recurso, antes, despues):
            # raise_on_error=True: si la auditoria falla, se revierte la operacion.
            log_event(
                request,
                accion,
                "SUCCESS",
                actor_user=request.user,
                resource_type="autorizador",
                resource_id=id_recurso,
                datos_antes=antes,
                datos_despues=despues,
                raise_on_error=True,
            )

        return registrar

    def _error_negocio(self, request, exc: AutorizadorError):
        return self._error(
            request, code=exc.code, message=exc.message, http_status=exc.http_status, details=exc.details,
        )

    def _error_validacion(self, request, serializer):
        return self._error(
            request,
            code="VALIDATION_ERROR",
            message="Datos de entrada inválidos",
            http_status=status.HTTP_400_BAD_REQUEST,
            details=serializer.errors,
        )

    def _respuesta_autorizador(self, autorizador, *, http_status=status.HTTP_200_OK):
        fresco = Repo.obtener(autorizador.pk)
        return Response({"autorizador": construir_autorizadores([fresco])[0]}, status=http_status)

    def _comun(self, request):
        return {
            "actor_id": _get_actor_id(request.user),
            "auditoria": self._auditoria(request),
            "identificador_peticion": self._identificador_peticion(request),
        }


class AutorizadorListaView(PaginationMixin, _BaseView):
    acciones = {"GET": "read", "POST": "create"}

    def _parametro_entero(self, request, nombre):
        valor = request.query_params.get(nombre)
        if valor in (None, ""):
            return None, None
        if not valor.isdigit():
            return None, self._error(
                request, code="VALIDATION_ERROR", message=f"Parámetro {nombre} inválido",
                http_status=status.HTTP_400_BAD_REQUEST, details={nombre: ["Debe ser un entero"]},
            )
        return int(valor), None

    def _parametro_opcion(self, request, nombre, opciones):
        valor = request.query_params.get(nombre) or None
        if valor is not None and valor not in opciones:
            return None, self._error(
                request, code="VALIDATION_ERROR", message=f"Parámetro {nombre} inválido",
                http_status=status.HTTP_400_BAD_REQUEST, details={nombre: [f"Permitidos: {', '.join(opciones)}"]},
            )
        return valor, None

    def _parametro_fecha(self, request, nombre):
        from datetime import date

        valor = request.query_params.get(nombre)
        if not valor:
            return None, None
        try:
            return date.fromisoformat(valor), None
        except ValueError:
            return None, self._error(
                request, code="VALIDATION_ERROR", message=f"Parámetro {nombre} inválido",
                http_status=status.HTTP_400_BAD_REQUEST, details={nombre: ["Formato AAAA-MM-DD"]},
            )

    def get(self, request):
        try:
            pagina, tamano = self._parse_pagination(request)
        except _PaginationError as exc:
            return exc.response

        id_usuario, error = self._parametro_entero(request, "usuarioId")
        if error:
            return error
        id_centro, error = self._parametro_entero(request, "centroId")
        if error:
            return error
        estatus, error = self._parametro_opcion(request, "estatus", Autorizador.Estatus.values)
        if error:
            return error
        vigencia, error = self._parametro_opcion(request, "vigencia", [e.value for e in EstadoVigencia])
        if error:
            return error
        clave_tipo, error = self._parametro_opcion(request, "tipo", TipoAutorizacion.Clave.values)
        if error:
            return error
        inicio_desde, error = self._parametro_fecha(request, "fechaInicioDesde")
        if error:
            return error
        fin_hasta, error = self._parametro_fecha(request, "fechaFinHasta")
        if error:
            return error

        consulta = Repo.listar(
            busqueda=(request.query_params.get("search") or "").strip() or None,
            id_usuario=id_usuario,
            clave_tipo=clave_tipo,
            id_centro=id_centro,
            estatus=estatus,
            vigencia=vigencia,
            fecha_inicio_desde=inicio_desde,
            fecha_fin_hasta=fin_hasta,
        )
        elementos, total, paginas = self._paginate_queryset(consulta, pagina, tamano)
        return self._paginated_response(construir_autorizadores(list(elementos)), pagina, tamano, total, paginas)

    def post(self, request):
        serializer = AutorizadorAltaSerializer(data=request.data)
        if not serializer.is_valid():
            return self._error_validacion(request, serializer)
        try:
            autorizador = UseCase.crear(
                serializer.validated_data,
                puede_otorgar_global=self._puede_otorgar_global(request),
                **self._comun(request),
            )
        except AutorizadorError as exc:
            return self._error_negocio(request, exc)
        return self._respuesta_autorizador(autorizador, http_status=status.HTTP_201_CREATED)


class AutorizadorDetalleView(_BaseView):
    acciones = {"GET": "read", "PATCH": "update"}

    def get(self, request, pk):
        autorizador = Repo.obtener(pk)
        if autorizador is None:
            return self._error(
                request, code="AUTHORIZER_NOT_FOUND", message="Autorizador no encontrado",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return self._respuesta_autorizador(autorizador)

    def patch(self, request, pk):
        serializer = AutorizadorEdicionSerializer(data=request.data)
        if not serializer.is_valid():
            return self._error_validacion(request, serializer)
        try:
            autorizador = UseCase.actualizar(
                pk,
                serializer.validated_data,
                puede_otorgar_global=self._puede_otorgar_global(request),
                **self._comun(request),
            )
        except AutorizadorError as exc:
            return self._error_negocio(request, exc)
        return self._respuesta_autorizador(autorizador)


class _AccionView(_BaseView):
    serializer_class = None
    caso_de_uso = None

    def post(self, request, pk):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return self._error_validacion(request, serializer)
        try:
            autorizador = type(self).caso_de_uso(pk, serializer.validated_data, **self._comun(request))
        except AutorizadorError as exc:
            return self._error_negocio(request, exc)
        return self._respuesta_autorizador(autorizador)


class AutorizadorSuspenderView(_AccionView):
    acciones = {"POST": "status"}
    serializer_class = CambioEstatusSerializer
    caso_de_uso = UseCase.suspender


class AutorizadorReactivarView(_AccionView):
    acciones = {"POST": "status"}
    serializer_class = VersionSerializer
    caso_de_uso = UseCase.reactivar


class AutorizadorBajaView(_AccionView):
    acciones = {"POST": "status"}
    serializer_class = CambioEstatusSerializer
    caso_de_uso = UseCase.dar_de_baja


class AutorizadorRenovarView(_AccionView):
    acciones = {"POST": "update"}
    serializer_class = RenovacionSerializer
    caso_de_uso = UseCase.renovar


class AutorizadorHistorialView(_BaseView):
    def get(self, request, pk):
        if Repo.obtener(pk) is None:
            return self._error(
                request, code="AUTHORIZER_NOT_FOUND", message="Autorizador no encontrado",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"items": [construir_movimiento(m) for m in Repo.movimientos(pk)]})


class UsuariosElegiblesView(_BaseView):
    def get(self, request):
        busqueda = (request.query_params.get("search") or "").strip() or None
        return Response({"items": [construir_usuario_elegible(u) for u in Repo.usuarios_elegibles(busqueda)]})


class CatalogosAutorizacionView(_BaseView):
    """Tipos de autorizacion y motivos para llenar la pantalla."""

    def get(self, request):
        tipos = TipoAutorizacion.objects.filter(esta_activo=True, fecha_baja__isnull=True).order_by("clave")
        motivos = Motivo.objects.filter(esta_activo=True).order_by("ambito", "id_motivo")
        return Response({
            "tipos": [
                {
                    "id": t.id_tipo_autorizacion,
                    "clave": t.clave,
                    "nombre": t.nombre,
                    "requiereCedula": t.requiere_cedula,
                    "modalidadPredeterminada": t.modalidad_predeterminada,
                }
                for t in tipos
            ],
            "motivos": [
                {
                    "id": m.id_motivo,
                    "ambito": m.ambito,
                    "clave": m.clave,
                    "descripcion": m.descripcion,
                    "requiereDescripcionLibre": m.requiere_descripcion_libre,
                }
                for m in motivos
            ],
        })
