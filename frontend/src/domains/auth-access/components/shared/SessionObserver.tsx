import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { authAPI } from "@api/resources/auth.api";
import { queryClient } from "@app/config/query-client";

import {
  applySessionExpiredState,
  expireSession,
} from "@/domains/auth-access/adapters/session-expiration";
import { subscribeSessionExpired } from "@/domains/auth-access/adapters/session-events";
import { authKeys } from "@/domains/auth-access/state/auth.keys";

// Intervalo del heartbeat. Debe ser menor al TTL de sesion activa del
// backend (ACTIVE_SESSION_TTL_SECONDS, default 30 min) para que el "sigo
// vivo" llegue antes de que Redis libere el slot por inactividad.
const SESSION_HEARTBEAT_INTERVAL_MS = 60_000;

// Eventos que cuentan como "el usuario sigue ahi". Si no hay ninguno de
// estos dentro de la ventana del heartbeat, se deja de renovar el TTL a
// proposito para que la sesion expire por inactividad real (no solo por
// tener la pestaña abierta).
const ACTIVITY_EVENTS = ["mousemove", "keydown", "click", "scroll", "touchstart"] as const;

const SESSION_EXPIRED_MESSAGE =
  "Tu sesión ha expirado. Por seguridad, inicia sesión nuevamente.";
// Id fijo: varias señales de expiracion casi simultaneas muestran un solo aviso.
const SESSION_EXPIRED_TOAST_ID = "session-expired";

export const SessionObserver = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const lastActivityRef = useRef(Date.now());

  useEffect(() => {
    const handleSessionExpired = () => {
      const isAlreadyOnLogin = location.pathname === "/login";

      // Idempotente: cubre tambien la expiracion avisada por otra pestaña.
      applySessionExpiredState();

      if (isAlreadyOnLogin) return;

      toast.error(SESSION_EXPIRED_MESSAGE, { id: SESSION_EXPIRED_TOAST_ID });
      // `from` permite volver a esta ruta despues de iniciar sesion.
      navigate("/login", { replace: true, state: { from: location } });
    };

    return subscribeSessionExpired(handleSessionExpired);
  }, [location, navigate]);

  useEffect(() => {
    let checkInFlight = false;

    // /auth/verify pasa por el interceptor: ante 401 ya intenta /auth/refresh
    // y, si la sesion no es renovable, dispara la expiracion. Un `valid:false`
    // que llegue hasta aca es un 401/403 definitivo.
    const checkSession = async () => {
      if (checkInFlight || !queryClient.getQueryData(authKeys.session())) return;
      checkInFlight = true;

      try {
        const result = await authAPI.verifyToken();
        if (result && !result.valid) {
          expireSession();
        }
      } catch {
        // Red caida, timeout o 5xx: no es evidencia de sesion expirada.
      } finally {
        checkInFlight = false;
      }
    };

    // Heartbeat: mantiene viva la sesion activa (control de sesion unica),
    // pero SOLO si hubo actividad real del usuario en la ultima ventana.
    // Si el usuario deja la pestaña abierta sin tocar nada, dejamos de
    // renovar el TTL a proposito para que la sesion expire por inactividad
    // real (antes solo se liberaba cerrando la pestaña o apagando el equipo).
    const markActivity = () => {
      const now = Date.now();
      const wasIdle = now - lastActivityRef.current > SESSION_HEARTBEAT_INTERVAL_MS;
      lastActivityRef.current = now;

      // Al volver de un periodo inactivo validamos de inmediato: si la sesion
      // murio mientras tanto, el usuario no debe seguir viendo la app hasta
      // el proximo tick.
      if (wasIdle) void checkSession();
    };
    ACTIVITY_EVENTS.forEach((event) =>
      window.addEventListener(event, markActivity, { passive: true }),
    );

    const interval = setInterval(() => {
      const idleFor = Date.now() - lastActivityRef.current;
      if (idleFor > SESSION_HEARTBEAT_INTERVAL_MS) return;
      void checkSession();
    }, SESSION_HEARTBEAT_INTERVAL_MS);

    return () => {
      ACTIVITY_EVENTS.forEach((event) =>
        window.removeEventListener(event, markActivity),
      );
      clearInterval(interval);
    };
  }, []);

  return null;
};
