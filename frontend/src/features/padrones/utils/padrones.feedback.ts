import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const PADRONES_ERROR_MESSAGES: Record<string, string> = {
  ALREADY_ENROLLED: "El paciente ya está inscrito en el padrón por ese padecimiento.",
  ENROLLMENT_NOT_FOUND: "La inscripción ya no existe.",
  ENROLLMENT_ALREADY_DISCHARGED: "La inscripción ya estaba dada de baja.",
  REGISTRY_NOT_FOUND: "Padrón no encontrado.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  ROLE_NOT_ALLOWED: "No tienes permiso para realizar esta acción.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getPadronesErrorMessage = (error: unknown, fallback: string) =>
  getCatalogErrorMessage(error, fallback, PADRONES_ERROR_MESSAGES);
