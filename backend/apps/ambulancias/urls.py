from django.urls import path

from apps.ambulancias.views import (
    AmbulanceRequestAuthorizeView,
    AmbulanceRequestCancelView,
    AmbulanceRequestRejectView,
    AmbulanceRequestReportView,
    AmbulanceRequestsListCreateView,
)

urlpatterns = [
    path("ambulance-requests", AmbulanceRequestsListCreateView.as_view(), name="ambulance-requests-list-create"),
    path("ambulance-requests/<int:request_id>/authorize", AmbulanceRequestAuthorizeView.as_view(), name="ambulance-request-authorize"),
    path("ambulance-requests/<int:request_id>/reject", AmbulanceRequestRejectView.as_view(), name="ambulance-request-reject"),
    path("ambulance-requests/<int:request_id>/cancel", AmbulanceRequestCancelView.as_view(), name="ambulance-request-cancel"),
    path("reportes/ambulancias", AmbulanceRequestReportView.as_view(), name="reportes-ambulancias"),
]
