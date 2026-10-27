from django.urls import path

from .views import (
    NotificacionContadorView,
    NotificacionLeidaView,
    NotificacionListaView,
    NotificacionMarcarTodasView,
)

urlpatterns = [
    path("notificaciones/", NotificacionListaView.as_view()),
    path("notificaciones/contador/", NotificacionContadorView.as_view()),
    path("notificaciones/marcar-todas-leidas/", NotificacionMarcarTodasView.as_view()),
    path("notificaciones/<int:pk>/leida/", NotificacionLeidaView.as_view()),
]
