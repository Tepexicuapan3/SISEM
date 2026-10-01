import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authAPI } from "@api/resources/auth.api";
import { authKeys } from "@/domains/auth-access/state/auth.keys";
import type { AuthUser } from "@api/types";
import { ApiError } from "@api/utils/errors";
import {
  clearAuthSession,
  setAuthSession,
} from "@/domains/auth-access/adapters/auth-cache";

/**
 * Query de sesion autenticada.
 *
 * Razon empresarial:
 * - Fuente unica de verdad para el usuario autenticado.
 * - Sesion cacheada hace permisos y guards deterministas.
 * - Respuesta no autorizada limpia cache y store para evitar acceso obsoleto.
 */
export const useAuthSession = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  const query = useQuery<AuthUser | null, ApiError>({
    queryKey: authKeys.session(),
    queryFn: () => authAPI.getCurrentUser(),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    retry: false,
  });

  useEffect(() => {
    if (!query.data) return;
    setAuthSession(queryClient, query.data);
  }, [query.data, queryClient]);

  useEffect(() => {
    if (!query.data) return;
    const requiresOnboarding = Boolean(
      query.data.requiresOnboarding ?? query.data.mustChangePassword,
    );

    if (requiresOnboarding && location.pathname !== "/onboarding") {
      navigate("/onboarding", { replace: true });
    }
  }, [location.pathname, navigate, query.data]);

  useEffect(() => {
    // React Query conserva el `data` previo cuando falla un refetch: un
    // 401/403 debe limpiar igual (fail-closed), si no la UI queda "logueada"
    // con un usuario obsoleto. Errores de red/5xx no entran aca.
    if (!query.error) return;
    if (query.error.status === 401 || query.error.status === 403) {
      clearAuthSession(queryClient);
    }
  }, [query.error, query.data, queryClient]);

  return query;
};
