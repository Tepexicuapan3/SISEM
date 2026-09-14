export interface SurgeryDiagnosisItem {
  id: number;
  cieCode: string;
  cieName: string;
}

export interface SurgeryItem {
  id: number;
  folio: string;
  noExp: string;
  pkNum: number;
  surgeonId: number;
  surgeonName: string | null;
  surgeryTypeId: number;
  surgeryTypeName: string;
  classificationId: number;
  classificationName: string;
  originClinicId: string | null;
  originClinicName: string | null;
  scheduledDate: string;
  scheduledTime: string;
  durationMinutes: number | null;
  contactPhone: string | null;
  description: string | null;
  diagnosisText: string | null;
  requirements: string | null;
  status: "activa" | "cancelada";
  performedStatus: "pendiente" | "realizada" | "no_realizada";
  diagnoses: SurgeryDiagnosisItem[];
  createdAt: string;
}

export interface SurgeryListParams {
  fechaInicio?: string;
  fechaFin?: string;
  surgeonId?: number;
  classificationId?: number;
  status?: string;
  noExp?: string;
}

export interface SurgeryListResponse {
  items: SurgeryItem[];
  total: number;
}

export interface ScheduleSurgeryRequest {
  noExp: string;
  pkNum?: number;
  surgeonId: number;
  surgeryTypeId: number;
  classificationId: number;
  originClinicId?: string;
  scheduledDate: string;
  scheduledTime: string;
  durationMinutes?: number;
  contactPhone?: string;
  description?: string;
  diagnosisText?: string;
  requirements?: string;
  cieCodes?: string[];
}

export interface CancelSurgeryRequest {
  reasonId: number;
  notes?: string;
}
