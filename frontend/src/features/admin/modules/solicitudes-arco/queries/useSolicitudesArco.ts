import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { arcoAPI } from "@api/resources/arco.api";
import type { ArcoRequestListParams } from "@api/types";

export const ARCO_QUERY_KEY = "solicitudes-arco";

export function useSolicitudesArco(params: ArcoRequestListParams) {
  return useQuery({
    queryKey: [ARCO_QUERY_KEY, params],
    queryFn: () => arcoAPI.getList(params),
    placeholderData: keepPreviousData,
  });
}
