import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const CIRUGIAS_ERROR_MESSAGES: Record<string, string> = {
  SURGERY_NOT_FOUND: "La cirugia ya no existe.",
  SURGERY_ALREADY_CANCELLED: "La cirugia ya esta cancelada.",
  SURGERY_TIME_CONFLICT: "El medico ya tiene una cirugia agendada que se traslapa con ese horario.",
  ROLE_NOT_ALLOWED: "No tienes permiso para realizar esta accion.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getCirugiasErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, CIRUGIAS_ERROR_MESSAGES);
};
