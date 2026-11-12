export interface PatientConsultationHistoryItem {
  visitId: number;
  // Estado de la visita: "cerrada" (nota vigente) | "cancelada" (nota cancelada
  // post-cierre, change `cancelacion-nota-cascada`).
  visitStatus: string;
  date: string | null;
  doctorId: number | null;
  doctorName: string | null;
  serviceType: string;
  primaryDiagnosis: string;
  cieCode: string | null;
  cieDescription: string | null;
  finalNote: string;
  // Nota SOAP, un campo por apartado (null si no se capturó).
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  // Indicaciones de texto libre de la receta.
  prescriptionItems: string[];
  // Medicamentos activos: lo que imprime la receta (decide el boton de imprimir).
  prescriptionMedications: string[];
  prescriptionFolio: string | null;
  // Ultima autorizacion de la receta (especial o controlado); null si no la pidio.
  prescriptionAuthorization: {
    status: "pendiente" | "autorizada" | "rechazada";
    rejectionReason: string | null;
  } | null;
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
