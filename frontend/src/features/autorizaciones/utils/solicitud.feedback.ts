import { ApiError } from "@api/utils/errors";

const MENSAJES: Record<string, string> = {
  REQUEST_NOT_FOUND: "La solicitud no existe o no tienes acceso a ella.",
  ALREADY_RESOLVED: "Esta solicitud ya fue resuelta. Se actualizó la pantalla.",
  STALE_VERSION: "La solicitud cambió mientras la revisabas. Revisa la información actualizada e intenta de nuevo.",
  DUPLICATE_DECISION: "Ya registraste tu decisión sobre esta solicitud.",
  REAUTH_FAILED: "La contraseña no es correcta. La decisión no se registró.",
  REAUTH_LOCKED: "Demasiados intentos fallidos. Espera unos minutos antes de volver a firmar.",
  REJECTION_NOT_ALLOWED: "Este tipo de autorización no admite rechazo.",
  REASON_REQUIRED: "Indica el motivo del rechazo.",
  RECIPIENT_NOT_ELIGIBLE: "Algunos autorizadores ya no pueden autorizar este tipo en este centro.",
  NO_ELIGIBLE_AUTHORIZERS: "No hay autorizadores elegibles para esta solicitud.",
  INSUFFICIENT_PERMISSIONS: "No tienes permiso para realizar esta acción.",
  SESSION_EXPIRED: "Tu sesión expiró. Inicia sesión nuevamente.",
  NETWORK_ERROR: "No hay conexión con el servidor. Intenta nuevamente.",
};

/** NOT_AUTHORIZED trae del servidor el motivo concreto (suspendido, sin el centro, etc.). */
export const getSolicitudErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) {
    return MENSAJES[error.code] ?? error.message ?? fallback;
  }
  return fallback;
};

export const esErrorDeConcurrencia = (error: unknown) =>
  error instanceof ApiError && ["ALREADY_RESOLVED", "STALE_VERSION", "DUPLICATE_DECISION"].includes(error.code);
