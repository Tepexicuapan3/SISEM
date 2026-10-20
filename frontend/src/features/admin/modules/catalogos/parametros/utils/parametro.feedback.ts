import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const PARAMETRO_ERROR_MESSAGES: Record<string, string> = {
  PARAMETER_NOT_FOUND: "El parámetro ya no existe o fue desactivado.",
  CENTER_NOT_FOUND: "El centro de atención no existe o está inactivo.",
  CENTER_VALUE_NOT_FOUND: "El centro ya no tenía un valor propio para este parámetro.",
  CENTER_OVERRIDE_NOT_ALLOWED: "Este parámetro es general: no admite valor por centro.",
  VALIDATION_ERROR: "Revisa el valor capturado antes de guardar.",
  INSUFFICIENT_PERMISSIONS: "No tienes permiso para modificar parámetros.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getParametroErrorMessage = (error: unknown, fallback: string) =>
  getCatalogErrorMessage(error, fallback, PARAMETRO_ERROR_MESSAGES);
