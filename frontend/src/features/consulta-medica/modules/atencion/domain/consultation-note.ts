import { ApiError } from "@api/utils/errors";

/**
 * "Iniciar consulta" solo cambia el estado de la visita: la nota de la consulta
 * se crea al guardar el diagnostico. Exploracion fisica, diagnosticos
 * secundarios y medicamentos cuelgan de esa nota.
 */
export const DIAGNOSIS_FIRST_MESSAGE =
  "Guarda el diagnóstico primero: la nota de la consulta se crea al guardarlo.";

export const isConsultationNoteMissing = (error: unknown): boolean =>
  error instanceof ApiError && error.code === "CONSULTATION_NOT_FOUND";
