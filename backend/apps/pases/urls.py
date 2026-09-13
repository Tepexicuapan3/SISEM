from django.urls import path

from apps.pases.views import (
    PatientReferralsHistoryView,
    ReferralCancelView,
    ReferralReportView,
    VisitReferralCreateView,
)

urlpatterns = [
    path(
        "visits/<int:visit_id>/referrals",
        VisitReferralCreateView.as_view(),
        name="visit-referral-create",
    ),
    path(
        "referrals/<int:referral_id>/cancel",
        ReferralCancelView.as_view(),
        name="referral-cancel",
    ),
    path(
        "patients/<str:no_exp>/referrals",
        PatientReferralsHistoryView.as_view(),
        name="patient-referrals-history",
    ),
    path(
        "reportes/pases",
        ReferralReportView.as_view(),
        name="reportes-pases",
    ),
]
