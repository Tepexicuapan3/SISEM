import { useQuery } from "@tanstack/react-query";
import { kardexAPI, existenciasAPI } from "@api/resources/almacen/kardex.api";
import type { ExistenciasListParams, KardexListParams } from "@api/types";
import { kardexKeys } from "./kardex.keys";

export function useKardexList(params: KardexListParams) {
  return useQuery({
    queryKey: kardexKeys.movList(params),
    queryFn:  () => kardexAPI.list(params),
    staleTime: 30_000,
  });
}

export function useExistenciasList(
  params: ExistenciasListParams,
  opts: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: kardexKeys.existList(params),
    queryFn:  () => existenciasAPI.list(params),
    staleTime: 30_000,
    enabled:  opts.enabled ?? true,
  });
}
