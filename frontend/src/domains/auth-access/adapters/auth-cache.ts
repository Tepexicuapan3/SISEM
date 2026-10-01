import type { QueryClient } from "@tanstack/react-query";
import type { AuthUser } from "@api/types";
import { authKeys } from "@/domains/auth-access/state/auth.keys";

/**
 * Sincroniza la sesion en React Query.
 *
 * Razon empresarial:
 * - Evita doble fuente de verdad.
 * - Garantiza que guards, UI y permisos lean el mismo usuario.
 */
export const setAuthSession = (queryClient: QueryClient, user: AuthUser) => {
  // Cachea la sesion para uso inmediato en queries.
  queryClient.setQueryData(authKeys.session(), user);
};

/**
 * Limpia por completo la sesion local.
 *
 * Razon empresarial:
 * - Protege contra estado obsoleto tras 401/403.
 * - Reduce riesgo de acceso visual con permisos caducados.
 */
export const clearAuthSession = (queryClient: QueryClient) => {
  // IMPORTANT:
  // No usamos removeQueries() porque si hay un useQuery montado (RootLayout),
  // eliminar la query provoca que se “recree” y refetchee -> bucles infinitos
  // (ej: /auth/me 401 -> refresh 401 -> clear -> refetch -> ...).
  // En su lugar, marcamos explicitamente “no autenticado”.

  queryClient.cancelQueries({ queryKey: authKeys.session() });
  queryClient.cancelQueries({ queryKey: authKeys.capabilities() });
  queryClient.setQueryData(authKeys.session(), null);
  queryClient.setQueryData(authKeys.capabilities(), null);
};

/**
 * Limpia todo dato cacheado bajo la sesion que expiro.
 *
 * Razon empresarial:
 * - Datos clinicos de la sesion anterior no deben quedar en memoria para el
 *   siguiente usuario de la misma estacion (igual que el logout manual).
 * - Las queries de auth se marcan como "no autenticado" en vez de removerse
 *   (ver clearAuthSession) para no provocar refetch en bucle.
 */
export const clearAuthenticatedCache = (queryClient: QueryClient) => {
  // removeQueries cancela en silencio los fetch en vuelo de cada query.
  queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== authKeys.all[0],
  });
  clearAuthSession(queryClient);
};
