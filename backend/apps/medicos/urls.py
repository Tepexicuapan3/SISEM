from django.urls import path

from apps.medicos.views.medico_import_views import (
    MedicoImportConfirmView,
    MedicoImportJobStatusView,
    MedicoImportPreviewView,
    MedicoImportTemplateView,
)
from apps.medicos.views.medico_views import (
    MedicosListCreateView,
    MedicoAsignarUsuarioView,
    MedicoDetailView,
    MedicoEspecialidadesView,
    MedicoCentrosView,
    MedicoConsultoriosView,
    MedicoConsultorioHorarioView,
    MedicoExcepcionesView,
    MedicoCoberturasView,
    MedicoCoberturaDetailView,
    MedicosDisponiblesView,
    MedicoDisponibilidadView,
    GenerarSlotsView,
)

urlpatterns = [
    # Catálogo
    path("medicos",                                           MedicosListCreateView.as_view(),       name="medicos-list-create"),

    # Import masivo (Excel) -- declarado ANTES de `<int:medico_id>` para
    # documentar intención (aunque "import" nunca matchea el converter
    # `int`, así que no hay colisión real de rutas posible).
    path("medicos/import/template",                           MedicoImportTemplateView.as_view(),     name="medico-import-template"),
    path("medicos/import/preview",                             MedicoImportPreviewView.as_view(),      name="medico-import-preview"),
    path("medicos/import/confirm",                             MedicoImportConfirmView.as_view(),      name="medico-import-confirm"),
    path("medicos/import/jobs/<uuid:job_id>",                  MedicoImportJobStatusView.as_view(),    name="medico-import-job"),

    path("medicos/<int:medico_id>",                             MedicoDetailView.as_view(),             name="medico-detail"),

    path("medicos/<int:medico_id>/asignar-usuario",              MedicoAsignarUsuarioView.as_view(),     name="medico-asignar-usuario"),

    # Disponibilidad (consumida por recepción y citas)
    path("medicos/disponibles",                               MedicosDisponiblesView.as_view(),       name="medicos-disponibles"),
    path("medicos/<int:medico_id>/disponibilidad",              MedicoDisponibilidadView.as_view(),     name="medico-disponibilidad"),

    # Sub-recursos
    path("medicos/<int:medico_id>/especialidades",              MedicoEspecialidadesView.as_view(),     name="medico-especialidades"),
    path("medicos/<int:medico_id>/especialidades/<int:especialidad_id>", MedicoEspecialidadesView.as_view(), name="medico-especialidad-delete"),
    path("medicos/<int:medico_id>/centros",                     MedicoCentrosView.as_view(),            name="medico-centros"),
    path("medicos/<int:medico_id>/centros/<int:rel_id>",        MedicoCentrosView.as_view(),            name="medico-centro-delete"),
    path("medicos/<int:medico_id>/consultorios",                MedicoConsultoriosView.as_view(),       name="medico-consultorios"),
    path("medicos/<int:medico_id>/consultorios/<int:rmc_id>",   MedicoConsultoriosView.as_view(),       name="medico-consultorio-delete"),
    path("medicos/<int:medico_id>/consultorios/<int:rmc_id>/horario", MedicoConsultorioHorarioView.as_view(), name="medico-consultorio-horario"),
    path("medicos/<int:medico_id>/excepciones",                 MedicoExcepcionesView.as_view(),        name="medico-excepciones"),
    path("medicos/<int:medico_id>/excepciones/<int:exc_id>",    MedicoExcepcionesView.as_view(),        name="medico-excepcion-delete"),
    path("coberturas",                                        MedicoCoberturasView.as_view(),         name="medico-coberturas"),
    path("coberturas/<int:cobertura_id>",                     MedicoCoberturaDetailView.as_view(),    name="medico-cobertura-detail"),
    path("medicos/<int:medico_id>/slots/generar",               GenerarSlotsView.as_view(),             name="medico-generar-slots"),
]
