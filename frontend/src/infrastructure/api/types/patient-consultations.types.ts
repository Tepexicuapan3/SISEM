export interface PatientConsultationHistoryItem {
  visitId: number;
  date: string | null;
  doctorId: number | null;
  doctorName: string | null;
  serviceType: string;
  primaryDiagnosis: string;
  cieCode: string | null;
  cieDescription: string | null;
  finalNote: string;
  prescriptionItems: string[];
  // Diagnosticos sensibles (change `diagnosticos-sensibles`): true cuando
  // el CIE-10 de esta consulta cae en un rango sensible (VIH/salud
  // mental/sustancias) y el usuario actual no tiene el permiso requerido
  // -- cieCode/cieDescription/primaryDiagnosis ya vienen redactados por el
  // backend, el resto del registro se sirve normal.
  restricted: boolean;
}

export interface PatientConsultationsHistoryResponse {
  items: PatientConsultationHistoryItem[];
  total: number;
  redactedVisitIds: number[];
}
