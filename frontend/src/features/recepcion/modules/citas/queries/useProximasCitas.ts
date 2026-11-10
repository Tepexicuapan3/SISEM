import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import type { ProximasCitasParams } from "@api/types";
import { CITAS_KEYS } from "./useCitasList";

export const useProximasCitas = (params: ProximasCitasParams, options?: { enabled?: boolean }) =>
  useQuery({
    queryKey: [...CITAS_KEYS.all, "proximas", params] as const,
    queryFn: () => citasAPI.getProximas(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
