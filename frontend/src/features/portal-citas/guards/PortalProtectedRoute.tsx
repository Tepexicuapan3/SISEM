import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { usePortalSessionStore } from "@app/state/portal/portalSessionStore";

interface Props {
  children: ReactNode;
}

/** Redirige a /portal/login si no hay una sesion de portal vigente. */
export const PortalProtectedRoute = ({ children }: Props) => {
  const accessToken = usePortalSessionStore((s) => s.accessToken);
  const isExpired = usePortalSessionStore((s) => s.isExpired());

  if (!accessToken || isExpired) {
    return <Navigate to="/portal/login" replace />;
  }

  return <>{children}</>;
};
