export type SecondaryDiagnosisStatus = "activo" | "cancelado";

export interface SecondaryDiagnosisItem {
  id: number;
  visitId: number;
  // Diagnosticos sensibles (change `diagnosticos-sensibles`): nullable
  // porque un diagnostico restringido llega con cieCode/cieDescription en
  // null y `restricted: true` (ver `PatientConsultationHistoryItem`).
  cieCode: string | null;
  cieDescription: string | null;
  notes: string | null;
  status: SecondaryDiagnosisStatus;
  createdAt: string;
  restricted: boolean;
}

export interface VisitSecondaryDiagnosesResponse {
  items: SecondaryDiagnosisItem[];
  total: number;
  redactedDiagnosisIds: number[];
}

export interface AddSecondaryDiagnosisRequest {
  cieCode: string;
  notes?: string;
}
