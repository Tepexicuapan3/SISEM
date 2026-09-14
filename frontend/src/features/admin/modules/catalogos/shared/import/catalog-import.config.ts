/**
 * Configuracion por catalogo del import masivo de Excel.
 *
 * `columns` debe reflejar exactamente los headers de `spec.columns` del
 * catalogo correspondiente en el backend
 * (`backend/apps/catalogos/imports/registry.py`): mismo orden, mismo texto.
 * Las filas que devuelve preview/confirm vienen indexadas por ese header
 * exacto (ej. "Clave", no "code"), asi que `key` debe coincidir con el
 * header tal cual.
 *
 * Un catalogo nuevo = una entrada nueva en el registro del backend + una
 * entrada nueva aca.
 */

export type CatalogImportColumnAlign = "left" | "center" | "right";

export interface CatalogImportColumnConfig {
  /** Header exacto tal como lo devuelve el backend (clave del row). */
  key: string;
  /** Etiqueta mostrada en el encabezado de la tabla de vista previa. */
  header: string;
  align?: CatalogImportColumnAlign;
  className?: string;
}

export interface CatalogImportConfig {
  /** Base de URL ya registrada en `routes` (urls.py), ej. "disabilities". */
  slug: string;
  /** Nombre legible del catalogo, usado en textos del dialog. */
  catalogLabel: string;
  /** Nombre de archivo sugerido al descargar la plantilla. */
  templateFilename: string;
  /** Columnas de datos (sin ERROR, se agrega aparte en la tabla). */
  columns: CatalogImportColumnConfig[];
}

export const DISCAPACIDADES_IMPORT_CONFIG: CatalogImportConfig = {
  slug: "disabilities",
  catalogLabel: "Discapacidades",
  templateFilename: "plantilla_discapacidades.xlsx",
  columns: [
    { key: "ID", header: "ID", align: "center", className: "w-[100px]" },
    { key: "Clave", header: "Clave", className: "w-[140px]" },
    { key: "Nombre", header: "Nombre" },
    { key: "Activo", header: "Activo", align: "center", className: "w-[120px]" },
  ],
};

export const ESPECIALIDADES_IMPORT_CONFIG: CatalogImportConfig = {
  slug: "specialties",
  catalogLabel: "Especialidades",
  templateFilename: "plantilla_especialidades.xlsx",
  columns: [
    { key: "ID", header: "ID", align: "center", className: "w-[100px]" },
    { key: "Nombre", header: "Nombre" },
    { key: "Activo", header: "Activo", align: "center", className: "w-[120px]" },
  ],
};

export const CIE9_MC_IMPORT_CONFIG: CatalogImportConfig = {
  slug: "cie9-mc",
  catalogLabel: "CIE-9-MC",
  templateFilename: "plantilla_cie9_mc.xlsx",
  columns: [
    { key: "ID", header: "ID", align: "center", className: "w-[100px]" },
    { key: "Clave", header: "Clave", className: "w-[140px]" },
    { key: "Descripcion", header: "Descripción" },
    { key: "Activo", header: "Activo", align: "center", className: "w-[120px]" },
  ],
};

export const ESCUELAS_IMPORT_CONFIG: CatalogImportConfig = {
  slug: "schools",
  catalogLabel: "Escuelas",
  templateFilename: "plantilla_escuelas.xlsx",
  columns: [
    { key: "ID", header: "ID", align: "center", className: "w-[100px]" },
    { key: "Clave", header: "Clave", className: "w-[140px]" },
    { key: "Nombre", header: "Nombre" },
    { key: "Activo", header: "Activo", align: "center", className: "w-[120px]" },
  ],
};
