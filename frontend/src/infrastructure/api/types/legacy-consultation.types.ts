/**
 * Historial de notas del legado (previas a SIRES) -- solo lectura.
 * Dos origenes con el mismo contrato base:
 *  - la copia del legado (sisem_legado), leida por persona en todas las bases:
 *    backend/apps/consulta_medica/services/legado_historial.py (trae medico,
 *    clinica, diagnosticos y `disponible`);
 *  - el archivo migrado de antes (sin copia configurada):
 *    backend/apps/consulta_medica/repositories/legacy_consultation_repository.py.
 */

export interface LegacyCie {
  /** null si el diagnostico es sensible y el usuario no tiene permiso. */
  codigo: string | null;
  descripcion: string | null;
}

export interface LegacyConsultationItem {
  id: number | string;
  legacyFolio: string;
  /** YYYY-MM-DD */
  date: string;
  time: string | null;
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  diagnosticImpression: string | null;
  addendumLegacy: string | null;
  weightLegacy: string | null;
  heightLegacy: string | null;
  bloodPressureLegacy: string | null;
  pulseLegacy: string | null;
  temperatureLegacy: string | null;
  // Solo desde la copia del legado:
  sourceDb?: string;
  doctorName?: string | null;
  clinicName?: string | null;
  primaryCie?: LegacyCie | null;
  diagnoses?: LegacyCie[];
  statusLegacy?: string | null;
  diagnosisRestricted?: boolean;
  // Solo desde el archivo migrado:
  doctorCodeLegacy?: string | null;
  clinicCodeLegacy?: number | null;
  primaryCieCodeLegacy?: number | null;
  isFirstVisitLegacy?: boolean | null;
}

export interface LegacyConsultationHistoryResponse {
  items: LegacyConsultationItem[];
  total: number;
  /** Conteo real en la base -- puede ser mayor a `total` si el backend recortó la lista. */
  totalCount: number;
  /** false: la copia del legado no respondió (se muestra `mensaje`). Ausente con el archivo migrado. */
  disponible?: boolean;
  mensaje?: string;
}
