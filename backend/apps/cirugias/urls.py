from django.urls import path

from apps.cirugias.views import SurgeriesListCreateView, SurgeryCancelView, SurgeryReportView

urlpatterns = [
    path("surgeries", SurgeriesListCreateView.as_view(), name="surgeries-list-create"),
    path("surgeries/<int:surgery_id>/cancel", SurgeryCancelView.as_view(), name="surgery-cancel"),
    path("reportes/cirugias", SurgeryReportView.as_view(), name="reportes-cirugias"),
]
