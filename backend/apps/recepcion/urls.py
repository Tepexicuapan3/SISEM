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
from apps.recepcion.views.adscripcion_views import (
    AdscripcionHistorialView,
    AdscripcionOpcionesView,
    AdscripcionPacienteView,
    AdscripcionPrevisualizarView,
    AdscripcionView,
    CitasPorReagendarView,
    ConsultorioFamiliarDetalleView,
    ConsultoriosFamiliaresView,
    DescartarCitaAfectadaView,
    EquivalenciaDetalleView,
    EquivalenciasView,
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

    # ── P-03 Adscripción a consultorio familiar ──────────────────────────────
    path("adscripcion",                                   AdscripcionView.as_view(),              name="adscripcion"),
    path("adscripcion/opciones",                          AdscripcionOpcionesView.as_view(),      name="adscripcion-opciones"),
    path("adscripcion/previsualizar",                     AdscripcionPrevisualizarView.as_view(), name="adscripcion-previsualizar"),
    path("adscripcion/pacientes/<int:id_paciente>",       AdscripcionPacienteView.as_view(),      name="adscripcion-paciente"),
    path("adscripcion/pacientes/<int:id_paciente>/historial", AdscripcionHistorialView.as_view(),  name="adscripcion-historial"),
    path("adscripcion/citas-por-reagendar",               CitasPorReagendarView.as_view(),        name="adscripcion-citas-por-reagendar"),
    path("adscripcion/citas-por-reagendar/<int:id_cita_afectada>/descartar",
         DescartarCitaAfectadaView.as_view(), name="adscripcion-cita-afectada-descartar"),
    path("adscripcion/config/clinicas",                   EquivalenciasView.as_view(),            name="adscripcion-config-clinicas"),
    path("adscripcion/config/clinicas/<int:id_clinica_centro>", EquivalenciaDetalleView.as_view(), name="adscripcion-config-clinica"),
    path("adscripcion/config/consultorios",               ConsultoriosFamiliaresView.as_view(),   name="adscripcion-config-consultorios"),
    path("adscripcion/config/consultorios/<int:id_adscripcion_consultorio>",
         ConsultorioFamiliarDetalleView.as_view(), name="adscripcion-config-consultorio"),
]
