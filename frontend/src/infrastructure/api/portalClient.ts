/**
 * Cliente HTTP del Portal de Citas (autoservicio del paciente).
 *
 * Instancia SEPARADA de `@api/client` a propósito: el cliente principal
 * usa cookies HttpOnly + refresh automático pensado para la sesión de
 * staff. El portal se autentica con `Authorization: Bearer <token>` (ver
 * backend/apps/portal_citas/authentication.py — deliberadamente sin
 * cookie, el portal puede vivir en otro dominio). Mezclar ambos clientes
 * arriesgaría que el interceptor de refresh del staff dispare sobre un 401
 * del portal, o que se manden cookies de staff a endpoints públicos.
 */

import axios from "axios";
import type { AxiosError, AxiosInstance } from "axios";

import { env } from "@app/config/env";
import { usePortalSessionStore } from "@app/state/portal/portalSessionStore";
import { ApiError, ERROR_CODES, type ApiErrorPayload } from "@api/utils/errors";

const portalClient: AxiosInstance = axios.create({
  baseURL: env.apiUrl,
  timeout: env.apiTimeout,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

portalClient.interceptors.request.use((config) => {
  const { accessToken } = usePortalSessionStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

function transformToApiError(error: AxiosError): ApiError {
  if (!error.response) {
    return new ApiError(
      ERROR_CODES.NETWORK_ERROR,
      error.message || "No hay conexión a internet",
      0,
    );
  }

  const { status, data } = error.response;
  const errorData = data as Partial<ApiErrorPayload>;

  return new ApiError(
    errorData?.code || (status === 401 ? ERROR_CODES.TOKEN_EXPIRED : ERROR_CODES.INTERNAL_SERVER_ERROR),
    errorData?.message || "Error del servidor, intenta nuevamente",
    status,
    errorData?.details,
    errorData?.requestId,
  );
}

portalClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token invalido/expirado -- limpiar sesion, el guard de rutas
      // (PortalProtectedRoute) redirige al login en el proximo render.
      usePortalSessionStore.getState().clearSession();
    }
    return Promise.reject(transformToApiError(error));
  },
);

export default portalClient;
