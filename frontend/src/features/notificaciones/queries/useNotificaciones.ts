import { useQuery } from "@tanstack/react-query";
import { notificacionesAPI } from "@api/resources/notificaciones/notificaciones.api";
import type { NotificacionesListParams } from "@api/types/notificaciones/notificaciones.types";

export const notificacionKeys = {
  all: ["notificaciones"] as const,
  list: (params: NotificacionesListParams) => [...notificacionKeys.all, "list", params] as const,
  contador: () => [...notificacionKeys.all, "contador"] as const,
};

/** El contador se refresca solo por si el socket se cae; el socket lo actualiza al instante. */
export const useContadorNotificaciones = () =>
  useQuery({
    queryKey: notificacionKeys.contador(),
    queryFn: notificacionesAPI.getContador,
    refetchInterval: 60 * 1000,
    staleTime: 15 * 1000,
  });

export const useNotificacionesList = (params: NotificacionesListParams, enabled = true) =>
  useQuery({
    queryKey: notificacionKeys.list(params),
    queryFn: () => notificacionesAPI.getAll(params),
    enabled,
    staleTime: 15 * 1000,
  });
