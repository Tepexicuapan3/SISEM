export type PrescriptionAuthorizationStatus = "pendiente" | "autorizada" | "rechazada";

export interface PrescriptionAuthorizationItem {
  id: number;
  prescriptionId: number;
  visitId: number;
  noExp: string;
  pkNum: number;
  prescribedById: number | null;
  medicationsCount: number;
  specializedCount: number;
  controlledCount: number;
  status: PrescriptionAuthorizationStatus;
  authorizedById: number | null;
  authorizedAt: string | null;
  rejectionReason: string | null;
  createdAt: string;
}

export interface PrescriptionAuthorizationListResponse {
  items: PrescriptionAuthorizationItem[];
  total: number;
}

export interface PrescriptionAuthorizationHistoryParams {
  estatus?: string;
  fechaInicio?: string;
  fechaFin?: string;
}

export interface RejectPrescriptionRequest {
  reason: string;
}
