/**
 * Datos del legado que el médico confirma antes de que pasen a SIRES.
 * Contrato: backend/apps/consulta_medica/services/legado_confirmacion.py y
 * views_legado.py (patients/<noExp>/legacy-review).
 */

export type LegacyReviewSectionKey =
  | "alergias"
  | "antecedentes_personales"
  | "antecedentes_familiares"
  | "antecedentes_quirurgicos"
  | "habitos";

export interface LegacyReviewItem {
  /** Base, tabla, fila y campo del legado de donde sale el dato. */
  ref: string;
  seccion: LegacyReviewSectionKey;
  texto: string;
  /** YYYY-MM-DD de la historia clínica del legado, si la tiene. */
  fecha: string | null;
  origen: string;
}

export interface LegacyReviewSection {
  seccion: LegacyReviewSectionKey;
  titulo: string;
  items: LegacyReviewItem[];
}

export interface LegacyReviewResponse {
  disponible: boolean;
  mensaje?: string;
  secciones: LegacyReviewSection[];
}

export interface ConfirmLegacyReviewRequest {
  seccion: LegacyReviewSectionKey;
  /** Referencias marcadas. Lo que se mostró sin marcar queda descartado. */
  aceptar: string[];
}

export interface ConfirmLegacyReviewResponse {
  confirmados: number;
  descartados: number;
}
