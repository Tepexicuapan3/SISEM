/**
 * Historia clinica unificada: registros permanentes del paciente
 * (antecedentes, habitos, tratamientos dentales), notas historicas de solo
 * lectura, exploracion fisica por consulta y catalogos clinicos.
 */
export type RecordSource = "general" | "stomatology" | "legacy";

interface PatientRecordBase {
  id: number;
  noExp: string;
  pkNum: number;
  source: RecordSource;
  createdAt: string;
  updatedAt: string | null;
  createdById: number | null;
}

/** Antecedentes con CIE-10 sensible llegan redactados sin permiso. */
interface CieRedactable {
  cieCode: string | null;
  cieDescription: string | null;
  description: string | null;
  isRestricted: boolean;
}

export interface PersonalHistoryItem extends PatientRecordBase, CieRedactable {
  diagnosisDate: string | null;
  /** A activo, R resuelto. */
  status: "A" | "R";
}

export interface FamilyHistoryItem extends PatientRecordBase, CieRedactable {
  relationshipId: string | null;
  relationshipName: string | null;
  isDeceased: boolean;
  causeOfDeath: string | null;
}

export interface SurgicalHistoryItem extends PatientRecordBase {
  procedure: string;
  procedureCie9Id: number | null;
  procedureCie9Code: string | null;
  approximateDate: string | null;
  place: string | null;
}

export interface HabitItem extends PatientRecordBase {
  habitId: number;
  habitCode: string;
  habitName: string;
  frequency: string | null;
  quantity: string | null;
  since: string | null;
  /** A actual, E ex. */
  status: "A" | "E";
  notes: string | null;
}

export interface DentalTreatmentItem extends PatientRecordBase {
  visitId: number | null;
  toothFdi: string | null;
  procedure: string;
  procedureCie9Id: number | null;
  procedureCie9Code: string | null;
  status: "planned" | "done";
  performedAt: string | null;
}

export interface RecordListResponse<T> {
  items: T[];
}

export type PatientRecordResource =
  | "personal-history"
  | "family-history"
  | "surgical-history"
  | "habits"
  | "dental-treatments";

export interface HistoricalNote {
  id: number;
  section: string;
  sectionLabel: string;
  specialty: RecordSource;
  notedOn: string | null;
  author: string | null;
  content: string;
  /** M migrado del sistema anterior, V version anterior de la historia. */
  origin: "M" | "V";
}

/**
 * Ultima medicion del sistema anterior ("sin consulta, fecha desconocida").
 * Cada valor es null si el texto original no era plausible; `rawText`
 * conserva siempre lo capturado. Decimales como string (DRF).
 */
export interface LegacyVitalSigns {
  id: number;
  specialty: RecordSource;
  measuredOn: string | null;
  weightKg: string | null;
  heightCm: string | null;
  bloodPressureSystolic: number | null;
  bloodPressureDiastolic: number | null;
  heartRateBpm: number | null;
  temperatureC: string | null;
  respiratoryRateBpm: number | null;
  bmi: string | null;
  rawText: string;
}

export interface HistoricalNotesResponse {
  legacyVitals: LegacyVitalSigns[];
  items: HistoricalNote[];
}

export interface PhysicalExamFinding {
  id: number;
  regionId: number;
  regionCode: string;
  regionName: string;
  isNormal: boolean;
  finding: string | null;
  updatedAt: string | null;
}

export interface PhysicalExamResponse {
  visitId: number;
  editable: boolean;
  items: PhysicalExamFinding[];
}

export interface SavePhysicalExamRequest {
  findings: { regionId: number; isNormal: boolean; finding?: string | null }[];
}

export interface ClinicalCatalogs {
  allergyTypes: { id: number; code: string; name: string }[];
  habits: { id: number; code: string; name: string }[];
  bodyRegions: { id: number; code: string; name: string }[];
  toothStates: { id: number; code: string; name: string; dmftComponent: "C" | "P" | "O" | null }[];
  teeth: { fdi: string; name: string; dentition: "P" | "T"; quadrant: number }[];
  relationships: { id: string; name: string }[];
}
