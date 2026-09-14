import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const AMBULANCIAS_ERROR_MESSAGES: Record<string, string> = {
  AMBULANCE_REQUEST_NOT_FOUND: "La solicitud ya no existe.",
  AMBULANCE_REQUEST_ALREADY_RESOLVED: "La solicitud ya fue autorizada o rechazada.",
  AMBULANCE_REQUEST_ALREADY_CANCELLED: "La solicitud ya esta dada de baja.",
  ROLE_NOT_ALLOWED: "No tienes permiso para realizar esta accion.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getAmbulanciasErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, AMBULANCIAS_ERROR_MESSAGES);
};
