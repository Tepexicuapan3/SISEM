import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const DESIGNACION_ERROR_MESSAGES: Record<string, string> = {
  DESIGNATION_NOT_FOUND: "La designación ya no existe o fue dada de baja.",
  DESIGNATION_EXISTS:
    "El usuario ya tiene una designación activa de ese tipo de autorización.",
  GLOBAL_PERMISSION_REQUIRED:
    "No tienes permiso para otorgar o modificar designaciones de todos los centros.",
  GLOBAL_REQUIRES_END_DATE:
    "El alcance de todos los centros exige fecha de fin de vigencia.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  PERMISSION_DENIED: "No tienes permiso para realizar esta accion.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getDesignacionErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, DESIGNACION_ERROR_MESSAGES);
};
