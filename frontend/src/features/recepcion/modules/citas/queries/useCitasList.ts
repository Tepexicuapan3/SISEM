import { useQuery } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import type { CitasListParams } from "@api/types";

const CITAS_KEYS = {
  all:   ["citas"]                                        as const,
  list:  (params?: CitasListParams) => ["citas", "list", params] as const,
  slots: (medicoId: number, fecha: string) => ["citas", "slots", medicoId, fecha] as const,
};

export { CITAS_KEYS };

export const useCitasList = (
  params?: CitasListParams,
  options?: { enabled?: boolean },
) =>
  useQuery({
    queryKey: CITAS_KEYS.list(params),
    queryFn:  () => citasAPI.getAll(params),
    staleTime: 30_000,
    enabled:   options?.enabled ?? true,
  });
