from django.urls import path

from .views import (
    AutorizadorBajaView,
    AutorizadorDetalleView,
    AutorizadorHistorialView,
    AutorizadorListaView,
    AutorizadorReactivarView,
    AutorizadorRenovarView,
    AutorizadorSuspenderView,
    CatalogosAutorizacionView,
    UsuariosElegiblesView,
)

from .views_solicitud import (
    SolicitudDecisionView,
    SolicitudDetalleView,
    SolicitudElegiblesView,
    SolicitudListaView,
    SolicitudNotificarView,
    MotivosRechazoView,
)

urlpatterns = [
    path("autorizaciones/solicitudes/", SolicitudListaView.as_view()),
    path("autorizaciones/motivos-rechazo/", MotivosRechazoView.as_view()),
    path("autorizaciones/solicitudes/<uuid:uuid_publico>/", SolicitudDetalleView.as_view()),
    path("autorizaciones/solicitudes/<uuid:uuid_publico>/decision/", SolicitudDecisionView.as_view()),
    path("autorizaciones/solicitudes/<uuid:uuid_publico>/elegibles/", SolicitudElegiblesView.as_view()),
    path("autorizaciones/solicitudes/<uuid:uuid_publico>/notificar/", SolicitudNotificarView.as_view()),
    path("autorizadores/", AutorizadorListaView.as_view()),
    path("autorizadores/usuarios-elegibles/", UsuariosElegiblesView.as_view()),
    path("autorizadores/<int:pk>/", AutorizadorDetalleView.as_view()),
    path("autorizadores/<int:pk>/suspender/", AutorizadorSuspenderView.as_view()),
    path("autorizadores/<int:pk>/reactivar/", AutorizadorReactivarView.as_view()),
    path("autorizadores/<int:pk>/baja/", AutorizadorBajaView.as_view()),
    path("autorizadores/<int:pk>/renovar/", AutorizadorRenovarView.as_view()),
    path("autorizadores/<int:pk>/historial/", AutorizadorHistorialView.as_view()),
    path("autorizaciones/catalogos/", CatalogosAutorizacionView.as_view()),
]
