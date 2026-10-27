"""API de la bandeja de notificaciones del usuario autenticado."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalogos.views import ErrorMixin, PaginationMixin, _PaginationError

from .permissions import SesionActiva
from .services import notificacion_service as servicio


class _BaseView(ErrorMixin, APIView):
    permission_classes = [SesionActiva]


class NotificacionListaView(PaginationMixin, _BaseView):
    def get(self, request):
        try:
            pagina, tamano = self._parse_pagination(request)
        except _PaginationError as exc:
            return exc.response
        solo_no_leidas = (request.query_params.get("soloNoLeidas") or "").lower() == "true"
        consulta = servicio.listar(request.user.id_usuario, solo_no_leidas=solo_no_leidas)
        elementos, total, paginas = self._paginate_queryset(consulta, pagina, tamano)
        return self._paginated_response([servicio.a_dict(n) for n in elementos], pagina, tamano, total, paginas)


class NotificacionContadorView(_BaseView):
    def get(self, request):
        return Response({"noLeidas": servicio.contar_no_leidas(request.user.id_usuario)})


class NotificacionLeidaView(_BaseView):
    def patch(self, request, pk):
        notificacion = servicio.marcar_leida(pk, request.user.id_usuario)
        if notificacion is None:
            return self._error(
                request, code="NOTIFICATION_NOT_FOUND", message="Notificación no encontrada",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"notificacion": servicio.a_dict(notificacion)})


class NotificacionMarcarTodasView(_BaseView):
    def post(self, request):
        return Response({"actualizadas": servicio.marcar_todas_leidas(request.user.id_usuario)})
