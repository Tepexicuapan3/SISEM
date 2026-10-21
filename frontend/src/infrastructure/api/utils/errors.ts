/**
 * API Error Utilities
 *
 * Clase ApiError y códigos de error estandarizados para SISEM.
 *
 * ¿POR QUÉ UNA CLASE CUSTOM?
 * Sin ApiError, cada componente interpreta errores diferente:
 *   - Uno chequea error.response?.status
 *   - Otro busca error.response?.data?.code
 *   - Otro asume que error.message existe
 *
 * Con ApiError, TODOS los errores tienen la misma forma:
 *   - error.code     → "TOKEN_EXPIRED"
 *   - error.message  → "Tu sesión expiró"
 *   - error.status   → 401
 *   - error.requestId → "abc-123" (para debugging)
 */

// ==========================================
// CÓDIGOS DE ERROR
// ==========================================

export const ERROR_CODES = {
  // Auth (4xx)
  INVALID_CREDENTIALS: "INVALID_CREDENTIALS",
  TOKEN_EXPIRED: "TOKEN_EXPIRED",
  TOKEN_INVALID: "TOKEN_INVALID",
  REFRESH_TOKEN_EXPIRED: "REFRESH_TOKEN_EXPIRED",
  SESSION_EXPIRED: "SESSION_EXPIRED",
  PERMISSION_DENIED: "PERMISSION_DENIED",
  ONBOARDING_REQUIRED: "ONBOARDING_REQUIRED",
  ACCOUNT_LOCKED: "ACCOUNT_LOCKED",
  USER_INACTIVE: "USER_INACTIVE",
  ACCOUNT_EXPIRED: "ACCOUNT_EXPIRED",
  SESSION_ALREADY_ACTIVE: "SESSION_ALREADY_ACTIVE",

  // Validación (400)
  VALIDATION_ERROR: "VALIDATION_ERROR",
  FIELD_REQUIRED: "FIELD_REQUIRED",
  INVALID_FORMAT: "INVALID_FORMAT",
  INVALID_EMAIL: "INVALID_EMAIL",
  PASSWORD_TOO_WEAK: "PASSWORD_TOO_WEAK",
  CODE_EXPIRED: "CODE_EXPIRED",
  INVALID_CODE: "INVALID_CODE",
  TERMS_NOT_ACCEPTED: "TERMS_NOT_ACCEPTED",

  // Lógica de negocio (4xx)
  NOT_FOUND: "NOT_FOUND", // Generic 404 fallback
  CONFLICT: "CONFLICT", // Generic 409 fallback
  USER_EXISTS: "USER_EXISTS",
  USER_NOT_FOUND: "USER_NOT_FOUND",
  ROLE_NOT_FOUND: "ROLE_NOT_FOUND",
  PERMISSION_NOT_FOUND: "PERMISSION_NOT_FOUND",
  CLINIC_NOT_FOUND: "CLINIC_NOT_FOUND",
  CANNOT_DELETE_SYSTEM_ROLE: "CANNOT_DELETE_SYSTEM_ROLE",
  CANNOT_REMOVE_LAST_ROLE: "CANNOT_REMOVE_LAST_ROLE",
  SELF_FORCE_LOGOUT_NOT_ALLOWED: "SELF_FORCE_LOGOUT_NOT_ALLOWED",
  USER_EMAIL_MISSING: "USER_EMAIL_MISSING",
  EMAIL_SEND_FAILED: "EMAIL_SEND_FAILED",

  // Sistema (5xx)
  INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
  DATABASE_ERROR: "DATABASE_ERROR",
  EXTERNAL_SERVICE_ERROR: "EXTERNAL_SERVICE_ERROR",
  SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
  ONBOARDING_FAILED: "ONBOARDING_FAILED",

  // Red (0)
  NETWORK_ERROR: "NETWORK_ERROR",
  RATE_LIMIT_EXCEEDED: "RATE_LIMIT_EXCEEDED",
  TIMEOUT_ERROR: "TIMEOUT_ERROR",
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

export type ApiErrorDetails = Record<string, string[] | string>;

export interface ApiErrorPayload {
  code: string;
  message: string;
  status: number;
  details?: ApiErrorDetails;
  requestId?: string;
}

// ==========================================
// MENSAJES USER-FRIENDLY
// ==========================================

export const ERROR_MESSAGES: Record<ErrorCode, string> = {
  [ERROR_CODES.INVALID_CREDENTIALS]: "Usuario o contraseña incorrectos",
  [ERROR_CODES.TOKEN_EXPIRED]: "Tu sesión ha expirado",
  [ERROR_CODES.TOKEN_INVALID]: "Token inválido",
  [ERROR_CODES.REFRESH_TOKEN_EXPIRED]: "Tu sesión ha expirado",
  [ERROR_CODES.SESSION_EXPIRED]: "Tu sesión ha expirado",
  [ERROR_CODES.PERMISSION_DENIED]: "No tienes permiso para esta acción",
  [ERROR_CODES.ONBOARDING_REQUIRED]:
    "Debes cambiar tu contraseña temporal y aceptar los términos antes de continuar",
  [ERROR_CODES.ACCOUNT_LOCKED]: "Cuenta bloqueada por intentos fallidos",
  [ERROR_CODES.USER_INACTIVE]: "Cuenta desactivada por un administrador",
  [ERROR_CODES.ACCOUNT_EXPIRED]: "Tu cuenta ha expirado. Contacta a soporte",
  [ERROR_CODES.SESSION_ALREADY_ACTIVE]:  "Tienes una sesión activa en otro equipo. Cerrar la sesión para continuar",
  [ERROR_CODES.VALIDATION_ERROR]: "Hay errores en el formulario",
  [ERROR_CODES.FIELD_REQUIRED]: "Faltan campos requeridos",
  [ERROR_CODES.INVALID_FORMAT]: "Formato inválido",
  [ERROR_CODES.INVALID_EMAIL]: "Email inválido",
  [ERROR_CODES.PASSWORD_TOO_WEAK]: "La contraseña es demasiado débil",
  [ERROR_CODES.CODE_EXPIRED]: "El código ha expirado o fue invalidado",
  [ERROR_CODES.INVALID_CODE]: "Código incorrecto",
  [ERROR_CODES.TERMS_NOT_ACCEPTED]: "Debes aceptar los términos y condiciones",
  [ERROR_CODES.NOT_FOUND]: "Recurso no encontrado", // Generic 404
  [ERROR_CODES.CONFLICT]: "El recurso ya existe o hay conflicto", // Generic 409
  [ERROR_CODES.USER_EXISTS]: "Ya existe un usuario con estos datos",
  [ERROR_CODES.USER_NOT_FOUND]: "Usuario no encontrado",
  [ERROR_CODES.ROLE_NOT_FOUND]: "Rol no encontrado",
  [ERROR_CODES.PERMISSION_NOT_FOUND]: "Permiso no encontrado",
  [ERROR_CODES.CLINIC_NOT_FOUND]: "Clinica no encontrada",
  [ERROR_CODES.CANNOT_DELETE_SYSTEM_ROLE]:
    "No se puede eliminar un rol de sistema",
  [ERROR_CODES.CANNOT_REMOVE_LAST_ROLE]:
    "El usuario debe conservar al menos un rol",
  [ERROR_CODES.SELF_FORCE_LOGOUT_NOT_ALLOWED]:
    "No puedes forzar el cierre de tu propia sesión",
  [ERROR_CODES.USER_EMAIL_MISSING]: "El usuario no tiene correo registrado",
  [ERROR_CODES.EMAIL_SEND_FAILED]:
    "No se pudo enviar el correo; la contraseña no fue modificada",
  [ERROR_CODES.INTERNAL_SERVER_ERROR]: "Error del servidor, intenta nuevamente",
  [ERROR_CODES.DATABASE_ERROR]: "Error de base de datos",
  [ERROR_CODES.EXTERNAL_SERVICE_ERROR]: "Error en servicio externo",
  [ERROR_CODES.SERVICE_UNAVAILABLE]: "Servicio temporalmente no disponible",
  [ERROR_CODES.ONBOARDING_FAILED]: "No se pudo completar el onboarding",
  [ERROR_CODES.NETWORK_ERROR]: "No hay conexión a internet",
  [ERROR_CODES.RATE_LIMIT_EXCEEDED]:
    "Demasiadas solicitudes, espera un momento",
  [ERROR_CODES.TIMEOUT_ERROR]: "La solicitud excedió el tiempo de espera",
};

// ==========================================
// CLASE ApiError
// ==========================================

/**
 * Error normalizado de la API de SISEM
 *
 * @example
 * ```typescript
 * try {
 *   await apiClient.post("/users", data);
 * } catch (error) {
 *   if (error instanceof ApiError) {
 *     console.log(error.code);      // "USER_EXISTS"
 *     console.log(error.message);   // "Ya existe un usuario..."
 *     console.log(error.requestId); // Para soporte técnico
 *   }
 * }
 * ```
 */
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly details?: ApiErrorDetails,
    public readonly requestId?: string,
    public readonly timestamp: Date = new Date(),
  ) {
    super(message);
    this.name = "ApiError";
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  /**
   * Obtiene mensaje user-friendly por código
   */
  static getMessage(code: ErrorCode): string {
    return ERROR_MESSAGES[code] || "Error desconocido";
  }
}

const EXPECTED_AUTH_ERROR_CODES = new Set<string>([
  ERROR_CODES.INVALID_CREDENTIALS,
  ERROR_CODES.TOKEN_EXPIRED,
  ERROR_CODES.TOKEN_INVALID,
  ERROR_CODES.SESSION_EXPIRED,
  ERROR_CODES.REFRESH_TOKEN_EXPIRED,
  ERROR_CODES.PERMISSION_DENIED,
  ERROR_CODES.ONBOARDING_REQUIRED,
]);

export const isExpectedAuthErrorForTelemetry = (error: unknown): boolean => {
  if (!(error instanceof ApiError)) {
    return false;
  }

  if (error.status !== 401 && error.status !== 403) {
    return false;
  }

  return EXPECTED_AUTH_ERROR_CODES.has(error.code);
};
