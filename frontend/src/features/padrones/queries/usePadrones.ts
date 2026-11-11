import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { padronesAPI } from "@api/resources/padrones.api";
import type {
  ChronicVisitEnrollRequest,
  PadronDischargeRequest,
  PadronEnrollRequest,
  PadronListParams,
  PadronRegistry,
} from "@api/types/padrones.types";

export const padronesKeys = {
  all: ["padrones"] as const,
  list: (registry: PadronRegistry, params: PadronListParams) =>
    [...padronesKeys.all, registry, "list", params] as const,
  options: (registry: PadronRegistry, search: string) =>
    [...padronesKeys.all, registry, "options", search] as const,
  chronicVisitNotice: (visitId: number, cie: string) =>
    [...padronesKeys.all, "cronicos", "visit-notice", visitId, cie] as const,
};

/** Aviso de cronicos de la consulta; `cie` es el diagnostico elegido (para la sugerencia). */
export const useChronicVisitNotice = (visitId: number, cie: string) =>
  useQuery({
    queryKey: padronesKeys.chronicVisitNotice(visitId, cie),
    queryFn: () => padronesAPI.chronicVisitNotice(visitId, cie),
    staleTime: 60 * 1000,
    // Sin permiso o sin padron el aviso simplemente no aparece: no reintentar.
    retry: false,
  });

export const useEnrollChronicFromVisit = (visitId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChronicVisitEnrollRequest) => padronesAPI.enrollChronicFromVisit(visitId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...padronesKeys.all, "cronicos"] });
    },
  });
};

export const usePadronList = (
  registry: PadronRegistry,
  params: PadronListParams,
  options: { enabled?: boolean } = {},
) =>
  useQuery({
    queryKey: padronesKeys.list(registry, params),
    queryFn: () => padronesAPI.list(registry, params),
    enabled: options.enabled ?? true,
  });

export const usePadronOptions = (registry: PadronRegistry, search: string, enabled: boolean) =>
  useQuery({
    queryKey: padronesKeys.options(registry, search),
    queryFn: () => padronesAPI.options(registry, search),
    enabled: enabled && search.trim().length >= 2,
    staleTime: 60 * 1000,
  });

export const useEnrollPadron = (registry: PadronRegistry) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PadronEnrollRequest) => padronesAPI.enroll(registry, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...padronesKeys.all, registry] });
    },
  });
};

export const useDischargePadron = (registry: PadronRegistry) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PadronDischargeRequest }) =>
      padronesAPI.discharge(registry, id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...padronesKeys.all, registry] });
    },
  });
};
