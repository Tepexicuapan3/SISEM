from django.urls import path

from apps.padrones.views import RegistryDischargeView, RegistryListCreateView, RegistryOptionsView

urlpatterns = [
    path("padrones/<str:registry>", RegistryListCreateView.as_view(), name="padrones-list-create"),
    path("padrones/<str:registry>/opciones", RegistryOptionsView.as_view(), name="padrones-options"),
    path(
        "padrones/<str:registry>/<int:enrollment_id>/baja",
        RegistryDischargeView.as_view(),
        name="padrones-discharge",
    ),
]
