import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const PRESCRIPTION_AUTH_ERROR_MESSAGES: Record<string, string> = {
  AUTHORIZATION_NOT_FOUND: "La autorizacion ya no existe.",
  AUTHORIZATION_ALREADY_RESOLVED: "Otro autorizador ya resolvio esta receta.",
  SELF_AUTHORIZATION_NOT_ALLOWED: "No puedes autorizar tu propia receta.",
  ROLE_NOT_ALLOWED: "No tienes permiso para autorizar recetas.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getPrescriptionAuthErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, PRESCRIPTION_AUTH_ERROR_MESSAGES);
};
