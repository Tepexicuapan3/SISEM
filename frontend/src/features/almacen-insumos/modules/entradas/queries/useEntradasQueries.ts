import { useQuery } from "@tanstack/react-query";
import { entradasAPI } from "@api/resources/almacen/kardex.api";
import type { EntradasListParams } from "@api/types";
import { entradasKeys } from "./entradas.keys";

export function useEntradasList(params: EntradasListParams) {
  return useQuery({
    queryKey: entradasKeys.list(params),
    queryFn:  () => entradasAPI.list(params),
    staleTime: 60_000,
  });
}
