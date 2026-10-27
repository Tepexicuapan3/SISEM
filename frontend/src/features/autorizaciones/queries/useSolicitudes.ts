import { useQuery } from "@tanstack/react-query";
import { solicitudesAPI } from "@api/resources/autorizaciones/solicitudes.api";
import type { SolicitudesListParams } from "@api/types/autorizaciones/solicitudes.types";

export const solicitudKeys = {
  all: ["autorizaciones", "solicitudes"] as const,
  list: (params: SolicitudesListParams) => [...solicitudKeys.all, "list", params] as const,
  detail: (uuid: string) => [...solicitudKeys.all, "detail", uuid] as const,
  elegibles: (uuid: string) => [...solicitudKeys.all, "elegibles", uuid] as const,
  motivosRechazo: () => ["autorizaciones", "motivos-rechazo"] as const,
};

export const useSolicitudesList = (params: SolicitudesListParams, enabled = true) =>
  useQuery({
    queryKey: solicitudKeys.list(params),
    queryFn: () => solicitudesAPI.getAll(params),
    enabled,
    staleTime: 15 * 1000,
  });

/** Detalle: se refresca seguido porque otro autorizador puede resolverla. */
export const useSolicitudDetalle = (uuid?: string) =>
  useQuery({
    queryKey: solicitudKeys.detail(uuid ?? ""),
    queryFn: () => solicitudesAPI.getByUuid(uuid as string),
    enabled: Boolean(uuid),
    staleTime: 5 * 1000,
    refetchInterval: 30 * 1000,
  });

export const useElegibles = (uuid: string, enabled: boolean) =>
  useQuery({
    queryKey: solicitudKeys.elegibles(uuid),
    queryFn: () => solicitudesAPI.getElegibles(uuid),
    enabled,
  });

export const useMotivosRechazo = (enabled = true) =>
  useQuery({
    queryKey: solicitudKeys.motivosRechazo(),
    queryFn: solicitudesAPI.getMotivosRechazo,
    enabled,
    staleTime: 10 * 60 * 1000,
  });
