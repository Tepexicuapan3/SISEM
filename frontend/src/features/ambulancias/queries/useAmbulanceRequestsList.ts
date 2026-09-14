import { useQuery } from "@tanstack/react-query";
import { ambulanciasAPI } from "@api/resources/ambulancias.api";
import type { AmbulanceRequestListParams } from "@api/types";

export function useAmbulanceRequestsList(
  params: AmbulanceRequestListParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["ambulancias", "list", params],
    queryFn: () => ambulanciasAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
