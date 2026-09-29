import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const ARCO_ERROR_MESSAGES: Record<string, string> = {
  NOT_FOUND: "La solicitud ya no existe.",
  ARCO_ALREADY_RESOLVED: "Otra persona ya resolvió esta solicitud.",
  INVALID_TRANSITION: "La solicitud cambió de estatus. Revisa su estado actual.",
  PERMISSION_DENIED: "No tienes permiso para gestionar solicitudes ARCO.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  SESSION_EXPIRED: "Tu sesión expiró. Inicia sesión nuevamente.",
  NETWORK_ERROR: "No hay conexión con el servidor. Intenta nuevamente.",
};

export const ARCO_NON_CRITICAL_CODES = new Set([
  "NOT_FOUND",
  "ARCO_ALREADY_RESOLVED",
  "INVALID_TRANSITION",
]);

export const getArcoErrorMessage = (error: unknown, fallback: string) =>
  getCatalogErrorMessage(error, fallback, ARCO_ERROR_MESSAGES);
