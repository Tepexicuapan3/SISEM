from django.urls import path

from apps.recepcion.views import PatientLookupView, PatientOpenView, VisitStatusLogView, VisitStatusView, VisitsView
from apps.recepcion.views.citas_views import (
    CitasListCreateView,
    CitaDetailView,
    CitaEstatusView,
    MotivosCancelacionView,
    SlotsDisponiblesView,
)
from apps.recepcion.views.agenda_views import AgendaSemanalView
from apps.recepcion.views.ficha_views import FichaVisitView
from apps.recepcion.views.qr_checkin_views import (
    CheckinCandidatosView,
    ConfirmarCheckinPorFolioView,
    ConfirmarQRCheckinView,
    VerificarQRView,
)
from apps.recepcion.views.turno_views import (
    TurnoFichaListCreateView, TurnoFichaDetailView, TurnoActualView,
)

urlpatterns = [
    # ── Visitas (check-in y cola de recepción) ────────────────────────────────
    path("visits",                          VisitsView.as_view(),        name="visits"),
    path("visits/<int:visit_id>/status",    VisitStatusView.as_view(),   name="visits-status"),
    path("visits/<int:visit_id>/ficha",       FichaVisitView.as_view(),       name="visits-ficha"),
    path("visits/<int:visit_id>/status-log", VisitStatusLogView.as_view(),   name="visits-status-log"),
    path("visits/patient-lookup",            PatientLookupView.as_view(),    name="visits-patient-lookup"),
    path("visits/patient-open",              PatientOpenView.as_view(),      name="visits-patient-open"),

    # ── Turnos de fichas ──────────────────────────────────────────────────────
    path("turnos-ficha",              TurnoFichaListCreateView.as_view(), name="turnos-ficha"),
    path("turnos-ficha/actual",       TurnoActualView.as_view(),          name="turno-actual"),
    path("turnos-ficha/<int:turno_id>", TurnoFichaDetailView.as_view(),   name="turno-ficha-detail"),

    # ── Citas médicas ─────────────────────────────────────────────────────────
    path("citas",                           CitasListCreateView.as_view(), name="citas"),
    path("citas/motivos-cancelacion",       MotivosCancelacionView.as_view(), name="citas-motivos-cancelacion"),
    path("citas/slots",                     SlotsDisponiblesView.as_view(),  name="citas-slots"),
    path("citas/agenda",                    AgendaSemanalView.as_view(),     name="citas-agenda"),
    path("citas/<int:cita_id>",             CitaDetailView.as_view(),      name="cita-detail"),
    path("citas/<int:cita_id>/estatus",     CitaEstatusView.as_view(),     name="cita-estatus"),

    # ── Check-in por QR (comprobante del portal) ─────────────────────────────
    path("citas/verificar-qr",              VerificarQRView.as_view(),        name="citas-verificar-qr"),
    path("citas/verificar-qr/confirmar",    ConfirmarQRCheckinView.as_view(), name="citas-verificar-qr-confirmar"),

    # ── Check-in manual (sin QR): por nombre de paciente o folio ─────────────
    path("citas/checkin/candidatos",        CheckinCandidatosView.as_view(),      name="citas-checkin-candidatos"),
    path("citas/checkin/confirmar-folio",   ConfirmarCheckinPorFolioView.as_view(), name="citas-checkin-confirmar-folio"),
]
