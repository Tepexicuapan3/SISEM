from django.urls import path

from apps.notificaciones.consumers import NotificacionesConsumer
from apps.realtime.consumers.visits import VisitsRealtimeConsumer

WS_VISITS_STREAM_ROUTE = "ws/v1/visits/stream"
WS_VISITS_STREAM_PATH = f"/{WS_VISITS_STREAM_ROUTE}"
WS_NOTIFICACIONES_STREAM_ROUTE = "ws/v1/notificaciones/stream"

websocket_urlpatterns = [
    path(WS_VISITS_STREAM_ROUTE, VisitsRealtimeConsumer.as_asgi()),
    path(WS_NOTIFICACIONES_STREAM_ROUTE, NotificacionesConsumer.as_asgi()),
]
