import { useQuery } from "@tanstack/react-query";
import { tipoTrasladoAPI } from "@api/resources/catalogos/tipos-traslado.api";
import type { TipoTrasladoDetailResponse } from "@api/types";
import { tipoTrasladoKeys } from "@features/admin/modules/catalogos/tipos-traslado/queries/tipos-traslado.keys";

export const useTipoTrasladoDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<TipoTrasladoDetailResponse>({
    queryKey: tipoTrasladoKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return tipoTrasladoAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
