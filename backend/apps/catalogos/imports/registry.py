from dataclasses import dataclass
from typing import Literal, Optional

from apps.catalogos.models import (
    CatCie9Mc,
    CatClasificacionCirugia,
    CatDestinoAmbulancia,
    CatMotivoCancelacionCirugia,
    CatMotivoTraslado,
    CatTipoCirugia,
    CatTipoServicioAmbulancia,
    CatTipoTraslado,
    Discapacidades,
    Escuelas,
    Especialidades,
)

ColumnKind = Literal["int_id", "text", "bool_si_no"]


@dataclass(frozen=True)
class ImportColumn:
    header: str
    field: str
    kind: ColumnKind
    required: bool = True
    max_length: Optional[int] = None
    unique_in_file: bool = False


@dataclass(frozen=True)
class CatalogImportSpec:
    slug: str
    # Distinto de `slug`: el string que ya usan CatalogPermissionMixin/_ACTION_MAP para
    # este catalogo (ej. "discapacidades"), mientras que `slug` es la base de URL ya
    # existente en routes (ej. "disabilities"). No se puede colapsar en un solo campo
    # porque el catalogo ya tiene ambos nombres viviendo en el codigo hoy.
    permission_catalog: str
    model: type
    pk_db_column: str
    columns: tuple  # tuple[ImportColumn, ...]
    sample_rows: tuple  # tuple[tuple, ...]
    max_rows: int = 5000


_DISABILITIES = CatalogImportSpec(
    slug="disabilities",
    permission_catalog="discapacidades",
    model=Discapacidades,
    pk_db_column="id_discapacidad",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Clave", field="code", kind="text", required=False, max_length=10),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=300),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "D01", "Discapacidad visual", "Si"),
        (2, "D02", "Discapacidad auditiva", "Si"),
    ),
)

_SPECIALTIES = CatalogImportSpec(
    slug="specialties",
    permission_catalog="especialidades",
    model=Especialidades,
    pk_db_column="id_espec",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=100),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Cardiología", "Si"),
        (2, "Pediatría", "Si"),
    ),
)

_SCHOOLS = CatalogImportSpec(
    slug="schools",
    permission_catalog="escuelas",
    model=Escuelas,
    pk_db_column="id_esc",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Clave", field="code", kind="text", required=False, max_length=45),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=100),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "ESC01", "Escuela de Enfermería Ejemplo", "Si"),
        (2, "ESC02", "Escuela de Medicina Ejemplo", "Si"),
    ),
)

# NOM-024-SSA3: catalogo de procedimientos CIE-9-MC (complementa CIE-10/CatCies, que
# solo cubre diagnosticos). No se cargan codigos reales aqui: el archivo oficial
# (DGIS/CENETEC) debe subirse por este mismo endpoint de import una vez disponible.
_CIE9_MC = CatalogImportSpec(
    slug="cie9-mc",
    permission_catalog="cie9_mc",
    model=CatCie9Mc,
    pk_db_column="id_cie9_mc",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Clave", field="code", kind="text", required=True, max_length=10),
        ImportColumn(header="Descripcion", field="name", kind="text", required=True, max_length=400),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "99.99", "Ejemplo de procedimiento CIE-9-MC", "Si"),
        (2, "89.03", "Ejemplo de consulta y evaluacion", "Si"),
    ),
)

_SURGERY_TYPES = CatalogImportSpec(
    slug="surgery-types",
    permission_catalog="tipos_cirugia",
    model=CatTipoCirugia,
    pk_db_column="id_tipo_cirugia",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Apendicectomia", "Si"),
        (2, "Colecistectomia", "Si"),
    ),
)

_SURGERY_CLASSIFICATIONS = CatalogImportSpec(
    slug="surgery-classifications",
    permission_catalog="clasificaciones_cirugia",
    model=CatClasificacionCirugia,
    pk_db_column="id_clasificacion_cirugia",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Cirugia corta", "Si"),
        (2, "Cirugia de quirofano", "Si"),
    ),
)

_SURGERY_CANCELLATION_REASONS = CatalogImportSpec(
    slug="surgery-cancellation-reasons",
    permission_catalog="motivos_cancelacion_cirugia",
    model=CatMotivoCancelacionCirugia,
    pk_db_column="id_motivo_cancelacion_cirugia",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Paciente no se presento", "Si"),
        (2, "Reprogramada por el medico", "Si"),
    ),
)

_TRANSFER_REASONS = CatalogImportSpec(
    slug="transfer-reasons",
    permission_catalog="motivos_traslado",
    model=CatMotivoTraslado,
    pk_db_column="id_motivo_traslado",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Consulta de especialidad", "Si"),
        (2, "Otro", "Si"),
    ),
)

_TRANSFER_TYPES = CatalogImportSpec(
    slug="transfer-types",
    permission_catalog="tipos_traslado",
    model=CatTipoTraslado,
    pk_db_column="id_tipo_traslado",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Ida y vuelta", "Si"),
        (2, "Solo ida", "Si"),
    ),
)

_AMBULANCE_SERVICE_TYPES = CatalogImportSpec(
    slug="ambulance-service-types",
    permission_catalog="tipos_servicio_ambulancia",
    model=CatTipoServicioAmbulancia,
    pk_db_column="id_tipo_servicio_ambulancia",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Basica", "Si"),
        (2, "Avanzada", "Si"),
    ),
)

_AMBULANCE_DESTINATIONS = CatalogImportSpec(
    slug="ambulance-destinations",
    permission_catalog="destinos_ambulancia",
    model=CatDestinoAmbulancia,
    pk_db_column="id_destino_ambulancia",
    columns=(
        ImportColumn(header="ID", field="id", kind="int_id", required=True, unique_in_file=True),
        ImportColumn(header="Nombre", field="name", kind="text", required=True, max_length=200),
        ImportColumn(header="Calle", field="street", kind="text", required=False, max_length=200),
        ImportColumn(header="CP", field="zip_code", kind="text", required=False, max_length=10),
        ImportColumn(header="Colonia", field="neighborhood", kind="text", required=False, max_length=150),
        ImportColumn(header="Delegacion", field="borough", kind="text", required=False, max_length=150),
        ImportColumn(header="Telefono", field="phone", kind="text", required=False, max_length=40),
        ImportColumn(header="Activo", field="is_active", kind="bool_si_no", required=False),
    ),
    sample_rows=(
        (1, "Hospital Central", "Av. Siempre Viva 1", "01000", "Centro", "Cuajimalpa", "5555555555", "Si"),
    ),
)

CATALOG_IMPORT_REGISTRY = {
    _DISABILITIES.slug: _DISABILITIES,
    _SPECIALTIES.slug: _SPECIALTIES,
    _SCHOOLS.slug: _SCHOOLS,
    _CIE9_MC.slug: _CIE9_MC,
    _SURGERY_TYPES.slug: _SURGERY_TYPES,
    _SURGERY_CLASSIFICATIONS.slug: _SURGERY_CLASSIFICATIONS,
    _SURGERY_CANCELLATION_REASONS.slug: _SURGERY_CANCELLATION_REASONS,
    _TRANSFER_REASONS.slug: _TRANSFER_REASONS,
    _TRANSFER_TYPES.slug: _TRANSFER_TYPES,
    _AMBULANCE_SERVICE_TYPES.slug: _AMBULANCE_SERVICE_TYPES,
    _AMBULANCE_DESTINATIONS.slug: _AMBULANCE_DESTINATIONS,
}
