import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { padronesAPI } from "@api/resources/padrones.api";
import type {
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
