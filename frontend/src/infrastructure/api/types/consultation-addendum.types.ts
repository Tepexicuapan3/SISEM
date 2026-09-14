/**
 * Nota de aclaración post-cierre de una consulta (NOM-004/024).
 * Contrato verificado contra
 * backend/apps/consulta_medica/{views,repositories/consultation_repository}.py.
 */

export interface ConsultationAddendum {
  id: number;
  consultationId: number;
  text: string;
  createdById: number | null;
  /** ISO 8601 */
  createdAt: string;
}

export interface ConsultationAddendaListResponse {
  items: ConsultationAddendum[];
  total: number;
}

export interface AddConsultationAddendumRequest {
  text: string;
}
