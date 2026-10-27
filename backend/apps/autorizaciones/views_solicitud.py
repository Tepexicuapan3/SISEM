"""API de la bandeja de autorizaciones (destino del boton de la notificacion).

Permisos (prefijo clinico:autorizaciones):
  GET bandeja y detalle -> read     POST decision -> decide
Tener el permiso no basta para decidir: la politica del autorizador se valida
dentro de la transaccion. El GET del detalle NUNCA cambia el estado de la
solicitud (solo marca "visto" al destinatario y deja la lectura en bitacora).
"""
from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.audit_service import log_event
from apps.authentication.services.response_service import get_client_ip, get_request_id
from apps.catalogos.permissions import HasCatalogPermission
from apps.catalogos.views import ErrorMixin, PaginationMixin, _PaginationError

from .models import Motivo, Solicitud, TipoAutorizacion
from .repositories.solicitud_repository import SolicitudRepository as Repo
from .serializers_solicitud import (
    DecisionSerializer,
    NotificarSerializer,
    construir_elegibles,
    construir_solicitud,
)
from .uses_case.solicitud_use_case import SolicitudError, SolicitudUseCase as UseCase

PERMISO_BASE = "clinico:autorizaciones"
RECURSO = "solicitud_autorizacion"


class _BaseView(ErrorMixin, APIView):
    accion = "read"

    def get_permissions(self):
        return [HasCatalogPermission(action=self.accion, catalog=PERMISO_BASE)]

    def _no_encontrada(self, request):
        return self._error(
            request, code="REQUEST_NOT_FOUND", message="Solicitud no encontrada",
            http_status=status.HTTP_404_NOT_FOUND,
        )

    def _visible(self, request, uuid_publico):
        solicitud = Repo.obtener(uuid_publico)
        if solicitud is None or not Repo.es_visible(solicitud, request.user.id_usuario):
            return None
        return solicitud


class SolicitudListaView(PaginationMixin, _BaseView):
    def _invalido(self, request, nombre, detalle):
        return self._error(
            request, code="VALIDATION_ERROR", message=f"Parámetro {nombre} inválido",
            http_status=status.HTTP_400_BAD_REQUEST, details={nombre: [detalle]},
        )

    def get(self, request):
        try:
            pagina, tamano = self._parse_pagination(request)
        except _PaginationError as exc:
            return exc.response

        params = request.query_params
        estatus = params.get("estatus") or None
        if estatus and estatus not in Solicitud.Estatus.values:
            return self._invalido(request, "estatus", f"Permitidos: {', '.join(Solicitud.Estatus.values)}")
        tipo = params.get("tipo") or None
        if tipo and tipo not in TipoAutorizacion.Clave.values:
            return self._invalido(request, "tipo", f"Permitidos: {', '.join(TipoAutorizacion.Clave.values)}")
        id_centro = params.get("centroId") or None
        if id_centro and not id_centro.isdigit():
            return self._invalido(request, "centroId", "Debe ser un entero")
        fechas = {}
        for nombre in ("desde", "hasta"):
            if valor := params.get(nombre):
                try:
                    fechas[nombre] = date.fromisoformat(valor)
                except ValueError:
                    return self._invalido(request, nombre, "Formato AAAA-MM-DD")

        consulta = Repo.listar_visibles(
            request.user.id_usuario,
            estatus=estatus,
            clave_tipo=tipo,
            id_centro=int(id_centro) if id_centro else None,
            folio=(params.get("folio") or "").strip() or None,
            **fechas,
        )
        elementos, total, paginas = self._paginate_queryset(consulta, pagina, tamano)
        datos = [construir_solicitud(s, id_usuario=request.user.id_usuario) for s in elementos]
        return self._paginated_response(datos, pagina, tamano, total, paginas)


class SolicitudDetalleView(_BaseView):
    def get(self, request, uuid_publico):
        solicitud = self._visible(request, uuid_publico)
        if solicitud is None:
            return self._no_encontrada(request)
        UseCase.marcar_vista(solicitud, request.user.id_usuario)
        # Lectura de informacion clinica: queda en la bitacora (NOM-024).
        log_event(
            request, "SolicitudConsultada", "SUCCESS", actor_user=request.user,
            resource_type=RECURSO, resource_id=solicitud.pk,
        )
        return Response({"solicitud": construir_solicitud(solicitud, id_usuario=request.user.id_usuario, detalle=True)})


class SolicitudDecisionView(_BaseView):
    accion = "decide"

    def post(self, request, uuid_publico):
        serializer = DecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return self._error(
                request, code="VALIDATION_ERROR", message="Datos de entrada inválidos",
                http_status=status.HTTP_400_BAD_REQUEST, details=serializer.errors,
            )

        def auditoria(accion, id_recurso, antes, despues):
            log_event(
                request, accion, "SUCCESS", actor_user=request.user, resource_type=RECURSO,
                resource_id=id_recurso, datos_antes=antes, datos_despues=despues, raise_on_error=True,
            )

        try:
            solicitud = UseCase.decidir(
                uuid_publico,
                serializer.validated_data,
                actor=request.user,
                auditoria=auditoria,
                ip=get_client_ip(request),
                agente_usuario=request.META.get("HTTP_USER_AGENT"),
                identificador_peticion=get_request_id(request),
            )
        except SolicitudError as exc:
            return self._error(
                request, code=exc.code, message=exc.message, http_status=exc.http_status, details=exc.details,
            )
        fresca = Repo.obtener(solicitud.uuid_publico)
        return Response({"solicitud": construir_solicitud(fresca, id_usuario=request.user.id_usuario, detalle=True)})


class SolicitudElegiblesView(_BaseView):
    """Autorizadores que hoy pueden autorizar la solicitud (para elegir a quien enviarla)."""

    accion = "notify"

    def get(self, request, uuid_publico):
        try:
            solicitud, elegibles = UseCase.elegibles(uuid_publico, actor=request.user)
        except SolicitudError as exc:
            return self._error(request, code=exc.code, message=exc.message, http_status=exc.http_status)
        return Response({"items": construir_elegibles(solicitud, elegibles)})


class SolicitudNotificarView(_BaseView):
    accion = "notify"

    def post(self, request, uuid_publico):
        serializer = NotificarSerializer(data=request.data)
        if not serializer.is_valid():
            return self._error(
                request, code="VALIDATION_ERROR", message="Datos de entrada inválidos",
                http_status=status.HTTP_400_BAD_REQUEST, details=serializer.errors,
            )

        def auditoria(accion, id_recurso, antes, despues):
            log_event(
                request, accion, "SUCCESS", actor_user=request.user, resource_type=RECURSO,
                resource_id=id_recurso, datos_antes=antes, datos_despues=despues, raise_on_error=True,
            )

        try:
            enviados = UseCase.notificar(
                uuid_publico, serializer.validated_data, actor=request.user, auditoria=auditoria,
            )
        except SolicitudError as exc:
            return self._error(
                request, code=exc.code, message=exc.message, http_status=exc.http_status, details=exc.details,
            )
        solicitud = Repo.obtener(uuid_publico)
        return Response({
            "notificados": len(enviados),
            "solicitud": construir_solicitud(solicitud, id_usuario=request.user.id_usuario, detalle=True),
        })


class MotivosRechazoView(_BaseView):
    """Motivos tipificados de rechazo para el dialogo de decision (lectura clinica;
    el catalogo completo de configuracion es de administracion)."""

    def get(self, request):
        motivos = Motivo.objects.filter(ambito=Motivo.Ambito.RECHAZO, esta_activo=True).order_by("id_motivo")
        return Response({
            "items": [
                {
                    "id": m.id_motivo,
                    "clave": m.clave,
                    "descripcion": m.descripcion,
                    "requiereDescripcionLibre": m.requiere_descripcion_libre,
                }
                for m in motivos
            ]
        })
