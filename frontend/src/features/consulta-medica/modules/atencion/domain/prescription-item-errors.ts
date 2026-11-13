import { ApiError } from "@api/utils/errors";
import { DIAGNOSIS_FIRST_MESSAGE } from "@features/consulta-medica/modules/atencion/domain/consultation-note";

const PRESCRIPTION_ITEM_ERROR_MESSAGE: Record<string, string> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para editar la receta.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  CONSULTATION_NOT_FOUND: DIAGNOSIS_FIRST_MESSAGE,
  PRESCRIPTION_ITEM_ALREADY_EXISTS: "Ese medicamento ya esta agregado en esta receta.",
  PRESCRIPTION_ITEM_NOT_FOUND: "El item de receta ya no existe.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

const FALLBACK_ERROR_MESSAGE = "No se pudo completar la accion. Intenta nuevamente.";

export const resolvePrescriptionItemError = (error: unknown): string => {
  if (!(error instanceof ApiError)) {
    return FALLBACK_ERROR_MESSAGE;
  }
  return PRESCRIPTION_ITEM_ERROR_MESSAGE[error.code] || error.message || FALLBACK_ERROR_MESSAGE;
};
