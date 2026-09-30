/**
 * Auth API Types
 * Tipos para autenticación, sesiones y recuperación de cuentas.
 *
 * @description Interfaces para login, logout, refresh, reset password y onboarding.
 * Todos los campos usan camelCase en inglés según el estándar de la API.
 */

import type { SuccessResponse } from "@api/types/common.types";

export const AUTH_USER_CONTRACT_FIELDS = {
  ID: "id",
  USERNAME: "username",
  FULL_NAME: "fullName",
  EMAIL: "email",
  AVATAR_URL: "avatarUrl",
  PRIMARY_ROLE: "primaryRole",
  LANDING_ROUTE: "landingRoute",
  ROLES: "roles",
  PERMISSIONS: "permissions",
  EFFECTIVE_PERMISSIONS: "effectivePermissions",
  CAPABILITIES: "capabilities",
  PERMISSION_DEPENDENCIES_VERSION: "permissionDependenciesVersion",
  STRICT_CAPABILITY_PREFIXES: "strictCapabilityPrefixes",
  AUTH_REVISION: "authRevision",
  MUST_CHANGE_PASSWORD: "mustChangePassword",
  REQUIRES_ONBOARDING: "requiresOnboarding",
} as const;

export const AUTH_CAPABILITY_STATE_FIELDS = {
  GRANTED: "granted",
  MISSING_ALL_OF: "missingAllOf",
  MISSING_ANY_OF: "missingAnyOf",
} as const;

// =============================================================================
// ENTIDADES BASE
// =============================================================================

/**
 * Usuario autenticado con permisos y configuración de sesión.
 * Contiene solo los datos necesarios para navegación y autorización en UI.
 */
export interface AuthUser {
  id: number;
  username: string;
  fullName: string;
  email: string;
  avatarUrl?: string | null;
  primaryRole: string;
  landingRoute: string | null;
  roles: string[];
  permissions: string[];
  effectivePermissions: string[];
  capabilities: Record<string, AuthCapabilityState>;
  permissionDependenciesVersion: string;
  strictCapabilityPrefixes: string[];
  authRevision: string;
  mustChangePassword: boolean;
  requiresOnboarding: boolean;
}

export interface AuthCapabilityState {
  granted: boolean;
  missingAllOf: string[];
  missingAnyOf: string[];
}

export interface AuthCapabilitiesResponse {
  permissions: string[];
  effectivePermissions: string[];
  capabilities: Record<string, AuthCapabilityState>;
  permissionDependenciesVersion: string;
  strictCapabilityPrefixes: string[];
  authRevision: string;
}

// =============================================================================
// REQUEST TYPES
// =============================================================================

/**
 * Payload para iniciar sesión.
 * POST /api/v1/auth/login
 */
export interface LoginRequest {
  username: string;
  password: string;
}

/**
 * Payload para solicitar código de recuperación de contraseña.
 * POST /api/v1/auth/request-reset-code
 */
export interface RequestResetCodeRequest {
  email: string;
}

/**
 * Payload para verificar código OTP de recuperación.
 * POST /api/v1/auth/verify-reset-code
 */
export interface VerifyResetCodeRequest {
  email: string;
  code: string;
}

/**
 * Payload para establecer nueva contraseña.
 * POST /api/v1/auth/reset-password
 */
export interface ResetPasswordRequest {
  newPassword: string;
}

/**
 * Payload para completar el proceso de onboarding.
 * POST /api/v1/auth/complete-onboarding
 */
export interface CompleteOnboardingRequest {
  newPassword: string;
  termsAccepted: boolean;
}

/**
 * Payload para cambio de contraseña autenticado.
 * POST /api/v1/auth/change-password
 */
export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

// =============================================================================
// RESPONSE TYPES
// =============================================================================

/**
 * Respuesta de login exitoso.
 * POST /api/v1/auth/login
 */
export interface LoginResponse {
  user: AuthUser;
  requiresOnboarding: boolean;
}

/**
 * Respuesta de refresh token exitoso.
 * POST /api/v1/auth/refresh
 * El nuevo access token se setea automáticamente en cookie HttpOnly.
 */
export type RefreshTokenResponse = SuccessResponse;

/**
 * Respuesta de verificación de código OTP.
 * POST /api/v1/auth/verify-reset-code
 */
export interface VerifyResetCodeResponse {
  valid: boolean;
}

/**
 * Respuesta de verificación de token JWT.
 * GET /api/v1/auth/verify
 */
export interface VerifyTokenResponse {
  valid: boolean;
}

/**
 * Respuesta de logout.
 * POST /api/v1/auth/logout
 */
export type LogoutResponse = SuccessResponse;

/**
 * Respuesta de solicitud de código de recuperación.
 * POST /api/v1/auth/request-reset-code
 */
export type RequestResetCodeResponse = SuccessResponse;

/**
 * Respuesta de reset de contraseña (retorna sesión activa).
 * POST /api/v1/auth/reset-password
 */
export type ResetPasswordResponse = LoginResponse;

/**
 * Respuesta de onboarding completado (retorna sesión activa).
 * POST /api/v1/auth/complete-onboarding
 */
export type CompleteOnboardingResponse = LoginResponse;

/**
 * Respuesta de cambio de contraseña.
 * POST /api/v1/auth/change-password
 */
export type ChangePasswordResponse = SuccessResponse;

/**
 * Respuesta de GET /api/v1/auth/me
 * Retorna el usuario autenticado actual.
 */
export type MeResponse = AuthUser;

/**
 * Respuesta de GET /api/v1/auth/capabilities
 * Retorna proyección de capacidades para decisiones UX de autorización.
 */
export type CapabilitiesResponse = AuthCapabilitiesResponse;
