import { queryClient } from "@app/config/query-client";
import { clearAuthenticatedCache } from "@/domains/auth-access/adapters/auth-cache";
import { emitSessionExpired } from "@/domains/auth-access/adapters/session-events";

/**
 * Expiracion definitiva de sesion (no confundir con logout voluntario).
 *
 * Razon empresarial:
 * - Un solo punto decide "la sesion ya no se puede renovar": interceptor,
 *   heartbeat y otras pestañas convergen aca.
 * - El latch evita tormentas de /auth/refresh y requests autenticados con
 *   credenciales que ya sabemos invalidas.
 * - El latch se libera solo cuando el backend vuelve a probar que hay sesion
 *   (login nuevo o /auth/me 200, ver error.interceptor).
 */
let sessionExpired = false;

export const isSessionExpired = () => sessionExpired;

export const markSessionAlive = () => {
  sessionExpired = false;
};

/**
 * Aplica el estado "sesion expirada" en esta pestaña sin notificar.
 * Idempotente: lo usa tambien el observer al recibir el evento de otra pestaña.
 */
export const applySessionExpiredState = () => {
  sessionExpired = true;
  clearAuthenticatedCache(queryClient);
};

/**
 * Expira la sesion una sola vez y (opcionalmente) notifica a la UI y a las
 * demas pestañas para mostrar el aviso y redirigir a /login.
 */
export const expireSession = ({ notify = true }: { notify?: boolean } = {}) => {
  if (sessionExpired) return;

  applySessionExpiredState();

  if (notify) {
    emitSessionExpired();
  }
};
