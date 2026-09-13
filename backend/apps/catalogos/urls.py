from django.urls import path

from .imports.registry import CATALOG_IMPORT_REGISTRY
from .views import *

routes = [
    ("authorizers", AutorizadoresListCreateView, AutorizadoresDetailView, "int"),
    ("discharge-reasons", BajasListCreateView, BajasDetailView, "int"),
    ("labor-quality", CalidadLaboralListCreateView, CalidadLaboralDetailView, "str"),
    ("consulting-rooms", ConsultoriosListCreateView, ConsultoriosDetailView, "int"),
    ("consultorios", ConsultoriosListCreateView, ConsultoriosDetailView, "int"),
    ("civil-status", EdoCivilListCreateView, EdoCivilDetailView, "int"),
    ("disabilities", DiscapacidadesListCreateView, DiscapacidadesDetailView, "int"),
    ("cie9-mc", Cie9McListCreateView, Cie9McDetailView, "int"),
    ("diseases", EnfermedadesListCreateView, EnfermedadesDetailView, "int"),
    ("education-level", EscolaridadListCreateView, EscolaridadDetailView, "int"),
    ("personal-types", TipoPersonalListCreateView, TipoPersonalDetailView, "int"),
    ("schools", EscuelasListCreateView, EscuelasDetailView, "int"),
    ("specialties", EspecialidadesListCreateView, EspecialidadesDetailView, "int"),
    ("med-studies", EstudiosMedListCreateView, EstudiosMedDetailView, "int"),
    ("med-groups", GruposDeMedicamentosListCreateView, GruposDeMedicamentosDetailView, "int"),
    ("medications", MedicamentosListCreateView, MedicamentosDetailView, "int"),
    ("occupations", OcupacionesListCreateView, OcupacionesDetailView, "int"),
    ("consultation-origins", OrigenConsListCreateView, OrigenConsDetailView, "str"),
    ("kinship", ParentescoListCreateView, ParentescoDetailView, "str"),
    ("passes", PasesListCreateView, PasesDetailView, "int"),
    ("areas", AreasListCreateView, AreasDetailView, "int"),
    ("area-types", TiposAreasListCreateView, TiposAreasDetailView, "int"),
    ("auth-types", TpAutorizacionListCreateView, TpAutorizacionDetailView, "int"),
    ("appointment-types", TipoDeCitasListCreateView, TipoDeCitasDetailView, "int"),
    ("consultation-types", TipoConsultaListCreateView, TipoConsultaDetailView, "int"),
    ("religions", ReligionListCreateView, ReligionDetailView, "int"),
    ("residence-types", TipoResidenciaListCreateView, TipoResidenciaDetailView, "int"),
    ("appointment-reasons", MotivoCitaListCreateView, MotivoCitaDetailView, "int"),
    ("licenses", LicenciasListCreateView, LicenciasDetailView, "int"),
    ("blood-type", TiposSanguineoListCreateView, TiposSanguineoDetailView, "int"),
    ("shifts", TurnosListCreateView, TurnosDetailView, "int"),
    ("vaccines", VacunasListCreateView, VacunasDetailView, "int"),
    ("clinical-areas", CatAreaClinicaListCreateView, CatAreaClinicaDetailView, "int"),
    ("branches", SucursalesListCreateView, SucursalDetailView, "int"),
    ("permisos", PermisosListCreateView, PermisosDetailView, "int"),
]

urlpatterns = []

for base, list_view, detail_view, pk_type in routes:
    urlpatterns.append(path(f"{base}/", list_view.as_view(), name=f"{base}-list-create"))
    urlpatterns.append(path(f"{base}/<{pk_type}:pk>/", detail_view.as_view(), name=f"{base}-detail"))


urlpatterns += [
    # CENTROS DE ATENCION
    path(
        "care-centers/",
        CentrosAtencionListCreateView.as_view(),
        name="care-centers-list-create",
    ),
    path(
        "care-centers/<int:pk>/",
        CentrosAtencionDetailView.as_view(),
        name="care-centers-detail",
    ),

    # HORARIOS DE CENTROS DE ATENCION
    path(
        "care-center-schedules/",
        CentrosAtencionHorariosListCreateView.as_view(),
        name="care-center-schedules-list-create",
    ),
    path(
        "care-center-schedules/<int:pk>/",
        CentrosAtencionHorariosDetailView.as_view(),
        name="care-center-schedules-detail",
    ),

    # EXCEPCIONES DE CENTROS DE ATENCION
    path(
        "care-center-exceptions/",
        CentrosAtencionExcepcionesListCreateView.as_view(),
        name="care-center-exceptions-list-create",
    ),
    path(
        "care-center-exceptions/<int:pk>/",
        CentrosAtencionExcepcionesDetailView.as_view(),
        name="care-center-exceptions-detail",
    ),

    # AREAS CLINICAS POR CENTRO
    path(
        "care-center-clinical-areas/",
        CentroAreaClinicaListCreateView.as_view(),
        name="care-center-clinical-areas-list-create",
    ),
    path(
        "care-center-clinical-areas/<int:center_id>/<int:area_id>/",
        CentroAreaClinicaDetailView.as_view(),
        name="care-center-clinical-areas-detail",
    ),

    # CODIGOS POSTALES
    path(
        "postal-codes/search/",
        CodigoPostalSearchAPIView.as_view(),
        name="postal-codes-search",
    ),

    # CIES
    path("cies/upload/", CatCiesUploadAPIView.as_view(), name="cies-upload"),
    path("cies/confirm/", CatCiesConfirmAPIView.as_view(), name="cies-confirm"),
    path("cies/", CatCiesListCreateView.as_view(), name="cies-list"),
    path("cies/<str:pk>/", CatCiesDetailView.as_view(), name="cies-detail"),
]

# IMPORT MASIVO DE CATALOGOS (Excel) — un catalogo nuevo en CATALOG_IMPORT_REGISTRY
# solo necesita su entrada ahi; estas 3 rutas por catalogo salen solas de este loop.
for _import_spec in CATALOG_IMPORT_REGISTRY.values():
    urlpatterns += [
        path(
            f"{_import_spec.slug}/import/template/",
            CatalogImportTemplateAPIView.as_view(spec=_import_spec, catalog=_import_spec.permission_catalog),
            name=f"{_import_spec.slug}-import-template",
        ),
        path(
            f"{_import_spec.slug}/import/preview/",
            CatalogImportPreviewAPIView.as_view(spec=_import_spec, catalog=_import_spec.permission_catalog),
            name=f"{_import_spec.slug}-import-preview",
        ),
        path(
            f"{_import_spec.slug}/import/confirm/",
            CatalogImportConfirmAPIView.as_view(spec=_import_spec, catalog=_import_spec.permission_catalog),
            name=f"{_import_spec.slug}-import-confirm",
        ),
    ]