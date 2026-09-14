/**
 * Historial de notas del legado (previas a SIRES) -- archivo de solo
 * lectura. Contrato verificado contra
 * backend/apps/consulta_medica/repositories/legacy_consultation_repository.py.
 */

export interface LegacyConsultationItem {
  id: number;
  legacyFolio: string;
  /** YYYY-MM-DD */
  date: string;
  time: string | null;
  doctorCodeLegacy: string | null;
  clinicCodeLegacy: number | null;
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  diagnosticImpression: string | null;
  primaryCieCodeLegacy: number | null;
  addendumLegacy: string | null;
  weightLegacy: string | null;
  heightLegacy: string | null;
  bloodPressureLegacy: string | null;
  pulseLegacy: string | null;
  temperatureLegacy: string | null;
  isFirstVisitLegacy: boolean | null;
}

export interface LegacyConsultationHistoryResponse {
  items: LegacyConsultationItem[];
  total: number;
  /** Conteo real en la base -- puede ser mayor a `total` si el backend recortó la lista. */
  totalCount: number;
}
