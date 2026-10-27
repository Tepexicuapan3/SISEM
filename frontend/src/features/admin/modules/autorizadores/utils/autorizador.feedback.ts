import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const MENSAJES: Record<string, string> = {
  AUTHORIZER_NOT_FOUND: "El autorizador ya no existe.",
  AUTHORIZER_EXISTS: "Ese usuario ya está registrado como autorizador.",
  AUTHORIZER_INACTIVE: "El autorizador está dado de baja y ya no se puede modificar.",
  STALE_VERSION: "Otra persona modificó este autorizador. Cierra y vuelve a abrir para ver los cambios.",
  INVALID_STATUS_TRANSITION: "Esa acción no aplica al estatus actual del autorizador.",
  USER_INVALID: "El usuario no existe o está inactivo.",
  CEDULA_REQUIRED:
    "El usuario no tiene cédula profesional. Captúrala en Usuarios antes de asignarlo como autorizador.",
  INVALID_VALIDITY: "Revisa las fechas de vigencia.",
  SCOPE_REQUIRED: "Cada tipo de autorización necesita al menos un centro.",
  REASON_REQUIRED: "Indica el motivo.",
  SELF_ADMIN_NOT_ALLOWED: "No puedes administrar tu propio registro de autorizador.",
  GLOBAL_PERMISSION_REQUIRED: "No tienes permiso para otorgar o modificar alcance de todos los centros.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de guardar.",
  INSUFFICIENT_PERMISSIONS: "No tienes permiso para realizar esta acción.",
  SESSION_EXPIRED: "Tu sesión expiró. Inicia sesión nuevamente.",
  NETWORK_ERROR: "No hay conexión con el servidor. Intenta nuevamente.",
};

export const getAutorizadorErrorMessage = (error: unknown, fallback: string) =>
  getCatalogErrorMessage(error, fallback, MENSAJES);
