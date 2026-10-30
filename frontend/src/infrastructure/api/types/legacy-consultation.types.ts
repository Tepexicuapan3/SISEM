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

/** Medicamento recetado en la nota (det_receta + cat_medicamentos). */
export interface LegacyMedication {
  name: string;
  activeIngredient: string | null;
  quantity: number | null;
  instructions: string | null;
  /** YYYY-MM-DD, null si no se surtió. */
  dispensedOn: string | null;
  cancelled: boolean;
}

/** Base del legado (una por año) donde el paciente tiene notas. */
export interface LegacyBase {
  /** legado_actual, legado_2024... */
  sourceDb: string;
  total: number;
  /** YYYY-MM-DD de la nota más vieja y la más nueva en esa base. */
  from: string | null;
  to: string | null;
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
  serviceName?: string | null;
  consultationType?: string | null;
  specialtyName?: string | null;
  medications?: LegacyMedication[];
  /** Días de cada incapacidad de la nota (det_licencia); `days` es texto si el legado no guardó un número. */
  sickLeaves?: { days: number | string | null; cancelled: boolean }[];
  /**
   * Pases de la nota: estudios de gabinete y laboratorio (det_pasgab/det_paslab
   * + cat_estudios), especialidad (pas_especialidad) y hospital (pas_hospital).
   */
  referralStudies?: {
    type: "GABINETE" | "LABORATORIO" | "ESPECIALIDAD" | "HOSPITAL";
    name: string;
    /** Lo que anotó el médico en el estudio (ds_complemento). */
    note: string | null;
    cancelled: boolean;
  }[];
  /** YYYY-MM-DD de la próxima cita que dejó el médico (his_notas.fe_cita). */
  nextAppointment?: string | null;
  respirationLegacy?: string | null;
  bmiLegacy?: string | null;
  glucoseLegacy?: string | null;
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
  /** Base de la que vienen los `items` (solo desde la copia del legado). */
  base?: string | null;
  /** Bases con notas; solo viene cuando se pidió sin `base`. */
  bases?: LegacyBase[];
}
