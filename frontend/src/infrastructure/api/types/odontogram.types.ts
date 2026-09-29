/**
 * Codigo de `cat_estado_pieza` (catalogo administrable; los valores de abajo
 * son los sembrados inicialmente). Se deja abierto a `string` para no
 * romper si estomatologia agrega estados nuevos.
 */
export type ToothCondition =
  | "healthy"
  | "caries"
  | "filled"
  | "crown"
  | "missing"
  | "extraction_needed"
  | "root_canal"
  | "sealant"
  | "fracture"
  | "implant"
  | (string & {});

/** "" = pieza completa; O/M/D/V/L = cara especifica. */
export type ToothFace = "" | "O" | "M" | "D" | "V" | "L";

export interface OdontogramFaceState {
  face: Exclude<ToothFace, "">;
  condition: ToothCondition;
  notes: string | null;
}

export interface OdontogramToothItem {
  toothFdi: string;
  condition: ToothCondition;
  notes: string | null;
  updatedAt: string | null;
  faces: OdontogramFaceState[];
}

export interface OdontogramDmft {
  decayed: number;
  missing: number;
  filled: number;
  index: number;
}

export interface OdontogramVersion {
  id: number;
  visitId: number | null;
  origin: "capture" | "migrated";
  dentition: "P" | "T" | "M";
  createdAt: string;
  createdById: number | null;
  dmft: OdontogramDmft;
}

export interface PatientOdontogramResponse {
  items: OdontogramToothItem[];
  version: OdontogramVersion | null;
}

export interface OdontogramVersionsResponse {
  items: OdontogramVersion[];
}

export interface UpdateOdontogramToothRequest {
  condition: ToothCondition;
  notes?: string | null;
  face?: ToothFace;
  visitId?: number | null;
}

export interface UpdateOdontogramToothResponse {
  toothFdi: string;
  face: ToothFace;
  condition: ToothCondition;
  notes: string | null;
  updatedAt: string;
  version: OdontogramVersion;
}

export type OdontogramDentition = "permanent" | "deciduous";
