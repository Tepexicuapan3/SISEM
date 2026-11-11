// Padrones clinicos (backend `padrones/<registry>`, P-04 del legado).

export type PadronRegistry = "cronicos" | "discapacidad";
export type PadronStatus = "activo" | "baja";

export interface PadronItemRef {
  /** CIE-10 (texto) en cronicos o id de discapacidad. null si el CIE esta restringido. */
  id: string | number | null;
  code: string | null;
  description: string;
  restricted: boolean;
}

export interface PadronEnrollment {
  id: number;
  registry: PadronRegistry;
  noExp: string;
  pkNum: number;
  patientName: string | null;
  item: PadronItemRef;
  center: { id: number; name: string };
  enrolledOn: string;
  enrolledBy: string | null;
  notes: string | null;
  status: PadronStatus;
  discharge: {
    reasonId: number;
    reason: string | null;
    detail: string | null;
    on: string;
    by: string | null;
  } | null;
}

export interface PadronListParams {
  noExp?: string;
  pkNum?: number;
  centerId?: number;
  status?: PadronStatus;
  page?: number;
  pageSize?: number;
}

export interface PadronListResponse {
  items: PadronEnrollment[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface PadronOption {
  id: string | number;
  code: string;
  description: string;
}

export interface PadronOptionsResponse {
  items: PadronOption[];
}

export interface PadronEnrollRequest {
  noExp: string;
  pkNum: number;
  itemId: string;
  centerId?: number | null;
  enrolledOn?: string | null;
  notes?: string | null;
}

export interface PadronDischargeRequest {
  reasonId: number;
  detail?: string | null;
  dischargedOn?: string | null;
}

// Aviso de cronicos dentro de la consulta (`padrones/cronicos/visita/<visitId>`).
// La regla de que CIE pertenece a que programa vive en el backend.

export interface ChronicProgramRef {
  code: string;
  name: string;
}

export interface ChronicNoticeEnrollment {
  id: number;
  item: PadronItemRef;
  /** null si el diagnostico esta restringido (el programa lo delataria). */
  program: ChronicProgramRef | null;
  enrolledOn: string;
}

export interface ChronicEnrollmentSuggestion {
  cie: { code: string; description: string };
  program: ChronicProgramRef;
}

export interface ChronicVisitNotice {
  enrollments: ChronicNoticeEnrollment[];
  suggestion: ChronicEnrollmentSuggestion | null;
  /** Tiene clinico:padrones:write: puede inscribir desde la consulta. */
  canEnroll: boolean;
}

export interface ChronicVisitEnrollRequest {
  itemId: string;
  notes?: string | null;
}
