import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { env } from "@app/config/env";
import { acquireRealtimeClient } from "@realtime/core/client";
import { notificacionKeys } from "@features/notificaciones/queries/useNotificaciones";

const RUTA_STREAM = "/ws/v1/notificaciones/stream";
const PUERTO_BACKEND_DEV = 5000;
const EVENTO = "notification.created";

/**
 * Misma regla que el stream de visitas: API absoluta -> su host; en desarrollo
 * con API relativa -> backend en VITE_BACKEND_PORT; si no, el host actual.
 */
export const resolverUrlNotificaciones = (): string => {
  const configurada = import.meta.env.VITE_NOTIFICACIONES_STREAM_URL;
  if (typeof configurada === "string" && configurada.trim()) return configurada.trim();

  const api = env.apiUrl;
  if (/^https?:\/\//i.test(api)) {
    const url = new URL(api);
    return `${url.protocol === "https:" ? "wss" : "ws"}://${url.host}${RUTA_STREAM}`;
  }
  if (typeof window === "undefined") return RUTA_STREAM;

  const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
  if (import.meta.env.DEV) {
    const puerto = Number(import.meta.env.VITE_BACKEND_PORT) || PUERTO_BACKEND_DEV;
    return `${protocolo}://${window.location.hostname}:${puerto}${RUTA_STREAM}`;
  }
  return `${protocolo}://${window.location.host}${RUTA_STREAM}`;
};

/**
 * Escucha las notificaciones del usuario (el backend solo publica al grupo
 * user.{id}). Solo refresca la bandeja y avisa: no toma ninguna decision.
 */
export const useNotificacionesRealtime = (enabled = true) => {
  const queryClient = useQueryClient();
  const navegar = useNavigate();

  useEffect(() => {
    if (!enabled || typeof WebSocket === "undefined") return;

    const lease = acquireRealtimeClient({ url: resolverUrlNotificaciones() });
    const dejarDeEscuchar = lease.client.subscribe(EVENTO, (evento) => {
      void queryClient.invalidateQueries({ queryKey: notificacionKeys.all });
      // Una solicitud nueva o resuelta tambien cambia la bandeja de autorizaciones.
      void queryClient.invalidateQueries({ queryKey: ["autorizaciones", "solicitudes"] });

      const datos = evento.payload as { titulo?: string; cuerpo?: string; urlAccion?: string };
      toast.info(datos.titulo ?? "Nueva notificación", {
        description: datos.cuerpo,
        action: datos.urlAccion
          ? { label: "Ver", onClick: () => navegar(datos.urlAccion as string) }
          : undefined,
      });
    });

    return () => {
      dejarDeEscuchar();
      lease.release();
    };
  }, [enabled, queryClient, navegar]);
};
