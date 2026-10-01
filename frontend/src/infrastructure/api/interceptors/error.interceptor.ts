/**
 * Error Interceptor
 *
 * Se ejecuta cuando el backend responde con error (4xx, 5xx) o hay fallo de red.
 *
 * RESPONSABILIDADES:
 * 1. Refresh automático de token en errores 401
 * 2. Transformar errores de Axios a ApiError (formato consistente)
 * 3. Logging en desarrollo (sin datos sensibles)
 *
 * ¿CÓMO FUNCIONA EL REFRESH?
 * 1. Request falla con 401 (token expirado)
 * 2. Si las credenciales ya rotaron desde que salió el request (otro refresh
 *    de esta u otra pestaña), se reintenta directo sin volver a refrescar
 * 3. Si no, POST /auth/refresh UNA sola vez: los 401 concurrentes comparten
 *    la misma promesa y, entre pestañas, se serializa con Web Locks
 * 4. Según el resultado del refresh:
 *    - refreshed   → reintentamos el request original (una sola vez)
 *    - expired     → 401/403 en /refresh: sesión no renovable → expireSession
 *    - no-session  → sin cookie CSRF: no hay sesión que renovar → expireSession
 *    - unavailable → red caída, timeout o 5xx: NO es expiración, no se cierra
 *                    sesión; se rechaza con un error de servicio no disponible
 * 5. Con la sesión expirada (latch) no se envían más requests autenticados
 *    hasta que el backend vuelva a probar sesión (login o /auth/me 200)
 *
 * ¿POR QUÉ ApiError?
 * Sin normalización, cada componente interpreta errores diferente.
 * Con ApiError, TODOS los errores tienen: code, message, status, requestId.
 */

import type {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from "axios";
import Cookies from "js-cookie";
import { ApiError, ERROR_CODES, type ApiErrorPayload } from "@api/utils/errors";
import { createRequestId } from "@api/utils/request-id";
import { queryClient } from "@app/config/query-client";
import { syncAuthSessionRevision } from "@/domains/auth-access/adapters/auth-session-sync";
import {
  expireSession,
  isSessionExpired,
  markSessionAlive,
} from "@/domains/auth-access/adapters/session-expiration";
import { authKeys } from "@/domains/auth-access/state/auth.keys";
import { env } from "@app/config/env";

const CSRF_COOKIE = "csrf_token";
const REFRESH_TIMEOUT_MS = Math.max(env.apiTimeout, 10_000);
const REFRESH_LOCK_NAME = "sisem:auth-refresh";

// Endpoints que NO deben intentar refresh (evita loops infinitos)
const NO_REFRESH_ENDPOINTS = [
  "/auth/login",
  "/auth/logout",
  "/auth/refresh",
  "/auth/reset-password",
  "/auth/complete-onboarding",
  "/auth/request-reset-code",
  "/auth/verify-reset-code",
];

// Respuestas 2xx que prueban que hay sesión válida (liberan el latch).
const SESSION_PROOF_ENDPOINTS = [
  "/auth/login",
  "/auth/me",
  "/auth/verify",
  "/auth/reset-password",
];

type RefreshOutcome = "refreshed" | "expired" | "no-session" | "unavailable";

type SessionAwareRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  /** Valor de la cookie CSRF al enviar: rota en cada login/refresh. */
  _csrfAtSend?: string;
};

// Refresh único compartido por todos los 401 concurrentes de esta pestaña.
let refreshPromise: Promise<RefreshOutcome> | null = null;

/**
 * Configura el interceptor de errores en el cliente Axios
 */
export function setupErrorInterceptor(client: AxiosInstance): void {
  client.interceptors.request.use((config: SessionAwareRequestConfig) => {
    // Sesión ya confirmada como no renovable: no seguir golpeando el backend
    // con credenciales inválidas. /auth/* queda libre para poder re-loguear.
    if (isSessionExpired() && !matchesEndpoint(config.url, "/auth/")) {
      throw new ApiError(
        ERROR_CODES.SESSION_EXPIRED,
        "Tu sesión ha expirado",
        401,
      );
    }

    config._csrfAtSend = Cookies.get(CSRF_COOKIE);
    return config;
  });

  client.interceptors.response.use(
    (response) => {
      if (
        SESSION_PROOF_ENDPOINTS.some((ep) =>
          matchesEndpoint(response.config?.url, ep, { exact: true }),
        )
      ) {
        markSessionAlive();
      }

      syncAuthSessionRevision({
        headers: response.headers,
        requestUrl: response.config?.url,
      });

      return response;
    },

    // Error: manejar 401 y transformar a ApiError
    async (error: AxiosError | ApiError) => {
      // Rechazado antes de salir (latch de sesión expirada): ya normalizado.
      if (error instanceof ApiError) {
        throw error;
      }

      const originalRequest = error.config as
        | SessionAwareRequestConfig
        | undefined;

      syncAuthSessionRevision({
        headers: error.response?.headers,
        requestUrl: originalRequest?.url,
      });

      const isRefreshableUnauthorized =
        error.response?.status === 401 &&
        originalRequest !== undefined &&
        !NO_REFRESH_ENDPOINTS.some((ep) =>
          matchesEndpoint(originalRequest.url, ep),
        );

      if (!isRefreshableUnauthorized) {
        throw transformToApiError(error);
      }

      // Ya se reintentó con credenciales renovadas y sigue 401 (o la sesión
      // ya se dio por expirada): no hay nada más que renovar.
      if (originalRequest._retry || isSessionExpired()) {
        expireSession();
        throw transformToApiError(error);
      }

      originalRequest._retry = true;
      const outcome = await resolveRefresh(originalRequest);

      if (outcome === "refreshed") {
        return client(originalRequest);
      }

      if (outcome === "expired" || outcome === "no-session") {
        // Sin cookie CSRF y sin usuario en caché es una visita sin sesión
        // (ej. primera carga): se limpia sin mostrar "sesión expirada".
        expireSession({
          notify: outcome === "expired" || hasCachedSession(),
        });
        throw transformToApiError(error);
      }

      // Red caída, timeout o 5xx al renovar: no es evidencia de expiración.
      throw new ApiError(
        ERROR_CODES.SERVICE_UNAVAILABLE,
        "No pudimos validar tu sesión en este momento. Intenta nuevamente.",
        503,
        undefined,
        resolveRequestId(error),
      );
    },
  );
}

/**
 * Decide si hace falta llamar a /auth/refresh y comparte una sola llamada
 * entre todos los 401 concurrentes.
 */
function resolveRefresh(
  request: SessionAwareRequestConfig,
): Promise<RefreshOutcome> {
  // Si la cookie CSRF cambió desde que salió el request, otro refresh (de
  // esta u otra pestaña) o un login nuevo ya rotó las credenciales: basta con
  // reintentar. Refrescar de nuevo con BLACKLIST_AFTER_ROTATION reusaría un
  // refresh token invalidado → 401 → logout de una sesión válida.
  const currentCsrf = Cookies.get(CSRF_COOKIE);
  if (
    request._csrfAtSend &&
    currentCsrf &&
    currentCsrf !== request._csrfAtSend
  ) {
    return Promise.resolve("refreshed");
  }

  if (!refreshPromise) {
    const requestId =
      (request.headers?.["X-Request-ID"] as string | undefined) ||
      createRequestId();

    // El lock se libera una única vez, cuando el refresh termina; los 401
    // que lleguen después caen en la comparación de CSRF de arriba.
    refreshPromise = refreshAcrossTabs(requestId).finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}

/**
 * Serializa el refresh entre pestañas (comparten cookies) con Web Locks.
 */
async function refreshAcrossTabs(requestId: string): Promise<RefreshOutcome> {
  const locks =
    typeof navigator !== "undefined" ? navigator.locks : undefined;

  if (!locks) {
    return performTokenRefresh(requestId);
  }

  const csrfBeforeLock = Cookies.get(CSRF_COOKIE);

  return locks.request(REFRESH_LOCK_NAME, async () => {
    const csrfAfterLock = Cookies.get(CSRF_COOKIE);
    // Otra pestaña renovó mientras esperábamos el lock.
    if (csrfBeforeLock && csrfAfterLock && csrfAfterLock !== csrfBeforeLock) {
      return "refreshed" as const;
    }
    return performTokenRefresh(requestId);
  });
}

/**
 * Llama a POST /auth/refresh y clasifica el resultado.
 * Nunca registra ni expone tokens: viajan solo en cookies HttpOnly.
 */
async function performTokenRefresh(requestId: string): Promise<RefreshOutcome> {
  const csrfToken = Cookies.get(CSRF_COOKIE);
  // Sin CSRF el backend rechaza el refresh: no hay sesión renovable.
  if (!csrfToken) {
    return "no-session";
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);

  try {
    const response = await fetch(`${env.apiUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include", // Envía cookies
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": requestId,
        "X-CSRF-TOKEN": csrfToken,
      },
      signal: controller.signal,
    });

    if (response.ok) {
      return "refreshed";
    }

    // 401: refresh vencido, revocado o sesión reemplazada/expirada en Redis.
    // 403: CSRF rechazado. Ninguno se arregla reintentando.
    if (response.status === 401 || response.status === 403) {
      return "expired";
    }

    // 5xx, 429, etc.: problema transitorio del servidor.
    return "unavailable";
  } catch {
    // Red caída o timeout (abort).
    return "unavailable";
  } finally {
    clearTimeout(timeoutId);
  }
}

function hasCachedSession(): boolean {
  return Boolean(queryClient.getQueryData(authKeys.session()));
}

function matchesEndpoint(
  url: string | undefined,
  endpoint: string,
  { exact = false }: { exact?: boolean } = {},
): boolean {
  if (!url) return false;
  const path = url.split("?")[0];
  return exact ? path.endsWith(endpoint) : path.includes(endpoint);
}

/**
 * Transforma AxiosError en ApiError normalizado
 */
function transformToApiError(error: AxiosError): ApiError {
  const requestId = resolveRequestId(error);

  // Error de red (sin conexión, timeout, etc.)
  if (!error.response) {
    return new ApiError(
      ERROR_CODES.NETWORK_ERROR,
      error.message || "No hay conexión a internet",
      0,
      undefined,
      requestId,
    );
  }

  // Error del backend
  const { status, data } = error.response;
  const errorData = data as Partial<ApiErrorPayload>;

  return new ApiError(
    (errorData?.code as keyof typeof ERROR_CODES) ||
      getDefaultErrorCode(status),
    errorData?.message || getDefaultMessage(status),
    status,
    errorData?.details,
    requestId,
  );
}

function resolveRequestId(error: AxiosError): string | undefined {
  const requestHeaderId = error.config?.headers?.["X-Request-ID"] as
    | string
    | undefined;
  if (requestHeaderId) {
    return requestHeaderId;
  }

  const responseData = error.response?.data as
    | { requestId?: unknown }
    | undefined;
  if (typeof responseData?.requestId === "string" && responseData.requestId) {
    return responseData.requestId;
  }

  const responseHeaders = error.response?.headers as
    | Record<string, unknown>
    | undefined;

  const responseHeaderId =
    responseHeaders?.["x-request-id"] ?? responseHeaders?.["X-Request-ID"];

  return typeof responseHeaderId === "string" && responseHeaderId
    ? responseHeaderId
    : undefined;
}

/**
 * Código de error por defecto según HTTP status
 *
 * IMPORTANTE: El backend siempre debe enviar `errorData.code` específico.
 * Estos defaults son solo fallback cuando el backend no informa código.
 */
function getDefaultErrorCode(status: number): string {
  switch (status) {
    case 400:
      return ERROR_CODES.VALIDATION_ERROR;
    case 401:
      return ERROR_CODES.TOKEN_EXPIRED;
    case 403:
      return ERROR_CODES.PERMISSION_DENIED;
    case 404:
      return ERROR_CODES.NOT_FOUND; // Generic fallback - backend debe especificar USER_NOT_FOUND/ROLE_NOT_FOUND/etc.
    case 409:
      return ERROR_CODES.CONFLICT; // Generic fallback - backend debe especificar USER_EXISTS/ROLE_EXISTS/etc.
    case 423:
      return ERROR_CODES.ACCOUNT_LOCKED;
    case 429:
      return ERROR_CODES.RATE_LIMIT_EXCEEDED;
    case 503:
      return ERROR_CODES.SERVICE_UNAVAILABLE;
    default:
      return ERROR_CODES.INTERNAL_SERVER_ERROR;
  }
}

/**
 * Mensaje por defecto según HTTP status
 */
function getDefaultMessage(status: number): string {
  switch (status) {
    case 400:
      return "Hay errores en el formulario";
    case 401:
      return "Sesión expirada";
    case 403:
      return "No tienes permiso para esta acción";
    case 404:
      return "Recurso no encontrado";
    case 409:
      return "El recurso ya existe";
    case 429:
      return "Demasiadas solicitudes, intenta en unos minutos";
    case 503:
      return "Servicio temporalmente no disponible";
    case 500:
      return "Error interno del servidor";
    default:
      return "Error desconocido";
  }
}
