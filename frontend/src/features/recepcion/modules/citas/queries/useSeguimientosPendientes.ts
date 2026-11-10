import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import type { SeguimientosPendientesParams } from "@api/types";
import { CITAS_KEYS } from "./useCitasList";

export const SEGUIMIENTOS_PENDIENTES_KEY = [...CITAS_KEYS.all, "seguimientos-pendientes"] as const;

export const useSeguimientosPendientes = (params: SeguimientosPendientesParams, options?: { enabled?: boolean }) =>
  useQuery({
    queryKey: [...SEGUIMIENTOS_PENDIENTES_KEY, params] as const,
    queryFn: () => citasAPI.getSeguimientosPendientes(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
