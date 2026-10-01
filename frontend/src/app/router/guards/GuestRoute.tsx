import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";
import { resolvePostLoginRedirect } from "@/domains/auth-access/adapters/login-redirect";
import { LoadingSpinner } from "@shared/components/LoadingSpinner";

interface GuestRouteProps {
  children: ReactNode;
}

export const GuestRoute = ({ children }: GuestRouteProps) => {
  const { data: sessionUser, isLoading } = useAuthSession();
  const location = useLocation();
  const isAuthenticated = Boolean(sessionUser);
  const requiresOnboarding = Boolean(
    sessionUser?.requiresOnboarding ?? sessionUser?.mustChangePassword,
  );

  if (isLoading && !sessionUser) {
    return <LoadingSpinner fullScreen />;
  }

  if (isAuthenticated) {
    if (requiresOnboarding) {
      return <Navigate to="/onboarding" replace />;
    }

    // Mismo destino que useLogin: evita que el guard pise la ruta de retorno.
    const landingRoute =
      resolvePostLoginRedirect(location.state) ??
      (sessionUser?.landingRoute && sessionUser.landingRoute !== "/login"
        ? sessionUser.landingRoute
        : "/dashboard");

    return <Navigate to={landingRoute} replace />;
  }

  return <>{children}</>;
};
