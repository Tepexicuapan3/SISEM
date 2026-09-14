import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { usePortalSessionStore } from "@app/state/portal/portalSessionStore";

interface Props {
  children: ReactNode;
}

/** Si ya hay sesion de portal vigente, saltea el login y va directo a Mis Citas. */
export const PortalGuestRoute = ({ children }: Props) => {
  const accessToken = usePortalSessionStore((s) => s.accessToken);
  const isExpired = usePortalSessionStore((s) => s.isExpired());

  if (accessToken && !isExpired) {
    return <Navigate to="/portal/mis-citas" replace />;
  }

  return <>{children}</>;
};
