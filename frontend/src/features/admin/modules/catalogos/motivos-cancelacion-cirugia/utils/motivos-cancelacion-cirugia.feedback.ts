import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const MOTIVOS_CANCELACION_CIRUGIA_ERROR_MESSAGES: Record<string, string> = {
  MOTIVOS_CANCELACION_CIRUGIA_NOT_FOUND: "El registro ya no existe o fue eliminado.",
  MOTIVOS_CANCELACION_CIRUGIA_EXISTS: "Ya existe un registro con ese nombre.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  PERMISSION_DENIED: "No tienes permiso para realizar esta accion.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getMotivoCancelacionCirugiaErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, MOTIVOS_CANCELACION_CIRUGIA_ERROR_MESSAGES);
};
