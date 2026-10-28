import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const MENSAJES: Record<string, string> = {
  CONFIG_INVALID: "Revisa los valores: hay una combinación que el sistema no permite.",
  STALE_VERSION: "Otra persona modificó este registro. Cierra y vuelve a abrir para ver los cambios.",
  TYPE_NOT_FOUND: "El tipo de autorización ya no existe.",
  RULE_NOT_FOUND: "La regla ya no existe o fue dada de baja.",
  RULE_EXISTS: "Ya hay una regla para ese tipo y centro; edítala en lugar de crear otra.",
  REASON_NOT_FOUND: "El motivo ya no existe.",
  REASON_EXISTS: "Ya existe un motivo con esa clave en este ámbito.",
  LAST_ACTIVE_REASON: "Debe quedar al menos un motivo activo en este ámbito.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  INSUFFICIENT_PERMISSIONS: "No tienes permiso para realizar esta acción.",
  SESSION_EXPIRED: "Tu sesión expiró. Inicia sesión nuevamente.",
  NETWORK_ERROR: "No hay conexión con el servidor. Intenta nuevamente.",
};

export const getConfiguracionErrorMessage = (error: unknown, fallback: string) =>
  getCatalogErrorMessage(error, fallback, MENSAJES);
