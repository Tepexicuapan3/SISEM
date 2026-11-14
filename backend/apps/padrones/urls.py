from django.urls import path

from apps.padrones.views import (
    ChronicVisitControlView,
    ChronicVisitEnrollView,
    ChronicVisitNoticeView,
    RegistryDischargeView,
    RegistryListCreateView,
    RegistryMembersView,
    RegistryOptionsView,
)

urlpatterns = [
    # Desde la consulta: antes que las rutas genericas <registry>.
    path(
        "padrones/cronicos/visita/<int:visit_id>/aviso",
        ChronicVisitNoticeView.as_view(),
        name="padrones-cronicos-visit-notice",
    ),
    path(
        "padrones/cronicos/visita/<int:visit_id>/control",
        ChronicVisitControlView.as_view(),
        name="padrones-cronicos-visit-control",
    ),
    path(
        "padrones/cronicos/visita/<int:visit_id>",
        ChronicVisitEnrollView.as_view(),
        name="padrones-cronicos-visit-enroll",
    ),
    path("padrones/miembros", RegistryMembersView.as_view(), name="padrones-members"),
    path("padrones/<str:registry>", RegistryListCreateView.as_view(), name="padrones-list-create"),
    path("padrones/<str:registry>/opciones", RegistryOptionsView.as_view(), name="padrones-options"),
    path(
        "padrones/<str:registry>/<int:enrollment_id>/baja",
        RegistryDischargeView.as_view(),
        name="padrones-discharge",
    ),
]
