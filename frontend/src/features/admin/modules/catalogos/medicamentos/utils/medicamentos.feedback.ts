import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const MEDICAMENTOS_ERROR_MESSAGES: Record<string, string> = {
  MEDICATIONS_NOT_FOUND: "El medicamento ya no existe o fue eliminado.",
  MEDICATIONS_EXISTS: "Ya existe un medicamento con ese nombre.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  PERMISSION_DENIED: "No tienes permiso para realizar esta accion.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getMedicamentoErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, MEDICAMENTOS_ERROR_MESSAGES);
};
