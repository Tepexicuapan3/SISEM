import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const CIE9_MC_ERROR_MESSAGES: Record<string, string> = {
  CIE9_MC_NOT_FOUND: "El registro ya no existe o fue eliminado.",
  CIE9_MC_EXISTS: "Ya existe un registro con esa clave.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  PERMISSION_DENIED: "No tienes permiso para realizar esta accion.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getCie9McErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, CIE9_MC_ERROR_MESSAGES);
};
