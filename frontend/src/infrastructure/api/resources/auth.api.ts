/**
 * Auth API Resource
 *
 * Gestión de autenticación, sesiones y recuperación de cuentas.
 * Estos endpoints son públicos.
 */

import apiClient from "@api/client";
import { AxiosError } from "axios";
import { ApiError } from "@api/utils/errors";

import type {
  LoginRequest,
  LoginResponse,
  RefreshTokenResponse,
  RequestResetCodeRequest,
  RequestResetCodeResponse,
  VerifyResetCodeRequest,
  VerifyResetCodeResponse,
  ResetPasswordRequest,
  ResetPasswordResponse,
  ChangePasswordRequest,
  ChangePasswordResponse,
  CompleteOnboardingRequest,
  CompleteOnboardingResponse,
  VerifyTokenResponse,
  LogoutResponse,
  MeResponse,
  CapabilitiesResponse,
} from "@api/types";

const authAPI = {
  /**
   * Iniciar sesión en el sistema.
   *
   * @endpoint POST /api/v1/auth/login
   * @permission Public
   *
   * @param data - Credenciales (username y password)
   * @returns Token, datos de usuario y flag de onboarding
   * @throws Error si las credenciales son inválidas o la respuesta es malformada
   */
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>("/auth/login", data);
    return response.data;
  },

  /**
   * Cerrar sesión actual.
   * Invalida el token en el servidor y limpia cookies.
   *
   * @endpoint POST /api/v1/auth/logout
   * @permission Auth (Token válido)
   */
  logout: async (): Promise<LogoutResponse> => {
    const response = await apiClient.post<LogoutResponse>("/auth/logout");
    return response.data;
  },

  /**
   * Obtener datos del usuario autenticado actual.
   * Se usa para hidratar la sesión al recargar la página.
   *
   * @endpoint GET /api/v1/auth/me
   * @permission Auth (Token válido)
   *
   * @returns Datos completos del usuario logueado
   */
  getCurrentUser: async (): Promise<MeResponse> => {
    const response = await apiClient.get<MeResponse>("/auth/me");
    return response.data;
  },

  /**
   * Obtener proyección de permisos/capabilities para UX de autorización.
   *
   * @endpoint GET /api/v1/auth/capabilities
   * @permission Auth (Token válido)
   */
  getCapabilities: async (): Promise<CapabilitiesResponse> => {
    const response =
      await apiClient.get<CapabilitiesResponse>("/auth/capabilities");
    return response.data;
  },

  /**
   * Verificar validez del token actual.
   * Útil para guardias de navegación o chequeos periódicos.
   *
   * @endpoint GET /api/v1/auth/verify
   * @permission Auth (Token válido)
   *
   * @returns true si el token es válido, false si es 401/403
   * @throws Error si ocurre un error de red o servidor (500)
   */
  verifyToken: async (): Promise<VerifyTokenResponse> => {
    try {
      await apiClient.get("/auth/verify");
      return { valid: true };
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401 || error.status === 403) {
          return { valid: false };
        }

        throw error;
      }

      const axiosError = error as AxiosError;

      if (
        axiosError.response &&
        (axiosError.response.status === 401 ||
          axiosError.response.status === 403)
      ) {
        return { valid: false };
      }

      throw error;
    }
  },

  /**
   * Renovar el token de acceso usando el refresh token (vía cookies).
   *
   * @endpoint POST /api/v1/auth/refresh
   * @permission Public (Usa Cookie HTTP-Only)
   */
  refreshToken: async (): Promise<RefreshTokenResponse> => {
    const response =
      await apiClient.post<RefreshTokenResponse>("/auth/refresh");
    return response.data;
  },

  // ===== ONBOARDING =====

  /**
   * Completar registro inicial (Onboarding).
   * Cambia contraseña temporal y acepta términos.
   *
   * @endpoint POST /api/v1/auth/complete-onboarding
   * @permission Auth (Token temporal válido)
   *
   * @param data - Nueva contraseña y aceptación de términos
   * @returns Nuevas credenciales definitivas
   */
  completeOnboarding: async (
    data: CompleteOnboardingRequest,
  ): Promise<CompleteOnboardingResponse> => {
    const response = await apiClient.post<CompleteOnboardingResponse>(
      "/auth/complete-onboarding",
      data,
    );
    return response.data;
  },

  // ===== RESET PASSWORD =====

  /**
   * Solicitar código de recuperación de contraseña.
   * Envía un email con el código OTP.
   *
   * @endpoint POST /api/v1/auth/request-reset-code
   * @permission Public
   *
   * @param data - Email del usuario
   */
  requestResetCode: async (
    data: RequestResetCodeRequest,
  ): Promise<RequestResetCodeResponse> => {
    const response = await apiClient.post<RequestResetCodeResponse>(
      "/auth/request-reset-code",
      data,
    );
    return response.data;
  },

  /**
   * Verificar código OTP de recuperación.
   * Retorna un token temporal para cambiar la contraseña.
   *
   * @endpoint POST /api/v1/auth/verify-reset-code
   * @permission Public
   *
   * @param data - Email y Código OTP
   * @returns Token temporal válido para reset-password
   */
  verifyResetCode: async (
    data: VerifyResetCodeRequest,
  ): Promise<VerifyResetCodeResponse> => {
    const response = await apiClient.post<VerifyResetCodeResponse>(
      "/auth/verify-reset-code",
      data,
    );
    return response.data;
  },

  /**
   * Establecer nueva contraseña usando token de recuperación.
   *
   * @endpoint POST /api/v1/auth/reset-password
   * @permission Auth (Token de recuperación válido)
   *
   * @param data - Nueva contraseña
   * @returns Auto-login con las nuevas credenciales
   */
  resetPassword: async (
    data: ResetPasswordRequest,
  ): Promise<ResetPasswordResponse> => {
    const response = await apiClient.post<ResetPasswordResponse>(
      "/auth/reset-password",
      data,
    );
    return response.data;
  },

  /**
   * Cambio de contraseña para sesión autenticada.
   *
   * @endpoint POST /api/v1/auth/change-password
   * @permission Auth (Token válido + CSRF)
   *
   * @param data - Contraseña actual y nueva contraseña
   * @returns Confirmación de operación exitosa. `sessionRotated === false`
   *          indica que la sesión no pudo rotarse y se debe avisar al usuario.
   */
  changePassword: async (
    data: ChangePasswordRequest,
  ): Promise<ChangePasswordResponse> => {
    const response = await apiClient.post<ChangePasswordResponse>(
      "/auth/change-password",
      data,
    );
    return response.data;
  },
};

export { authAPI };
