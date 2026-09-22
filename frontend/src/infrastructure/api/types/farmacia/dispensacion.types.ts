/**
 * Dispensación de Farmacia — tipos (sdd/dispensacion-farmacia).
 *
 * Contrato exacto del backend: consulta_medica/serializers.py
 * (DispensePrescriptionSerializer) y
 * consulta_medica/uses_case/prescription_dispensation_usecase.py.
 */

// =============================================================================
// ENUMS
// =============================================================================

export const DISPENSATION_STATUS = {
  PENDIENTE: "pendiente",
  PARCIAL: "parcial",
  DISPENSADO: "dispensado",
} as const;

export type DispensationStatus = (typeof DISPENSATION_STATUS)[keyof typeof DISPENSATION_STATUS];

export const DISPENSATION_STATUS_LABELS: Record<DispensationStatus, string> = {
  pendiente: "Pendiente",
  parcial: "Parcial",
  dispensado: "Dispensado",
};

// =============================================================================
// ENTIDADES
// =============================================================================

export interface DispensationQueueItem {
  prescriptionId: number;
  visitId: number;
  noExp: string | null;
  pkNum: number;
  patientName: string | null;
}

export interface DispensationPreviewItem {
  itemId: number;
  medicationId: number;
  medicationName: string;
  presentation: string | null;
  dose: string | null;
  indications: string;
  quantity: number;
  dispensedQuantity: number;
  pendingQuantity: number;
  dispensationStatus: DispensationStatus;
  hasMapping: boolean;
  factorConversion: string | null;
  permiteFraccion: boolean | null;
  computedQuantity: string | null;
}

export interface DispensationResultItem {
  itemId: number;
  dispensedQuantity: number;
  dispensationStatus: DispensationStatus;
}

// =============================================================================
// REQUESTS
// =============================================================================

export interface DispensePrescriptionItemRequest {
  itemId: number;
  quantity: number;
}

export interface DispensePrescriptionRequest {
  idAlmacen: number;
  items: DispensePrescriptionItemRequest[];
}

// =============================================================================
// RESPONSES
// =============================================================================

export interface DispensationQueueResponse {
  items: DispensationQueueItem[];
  total: number;
}

export interface DispensationPreviewResponse {
  prescriptionId: number;
  visitId: number;
  items: DispensationPreviewItem[];
}

export interface DispensePrescriptionResponse {
  prescriptionId: number;
  idAlmacen: number;
  items: DispensationResultItem[];
}

// =============================================================================
// PARAMS
// =============================================================================

export interface DispensationQueueParams {
  idAlmacen?: number;
}
