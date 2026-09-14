import { useQuery } from "@tanstack/react-query";
import { motivoTrasladoAPI } from "@api/resources/catalogos/motivos-traslado.api";
import type { MotivoTrasladoDetailResponse } from "@api/types";
import { motivoTrasladoKeys } from "@features/admin/modules/catalogos/motivos-traslado/queries/motivos-traslado.keys";

export const useMotivoTrasladoDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<MotivoTrasladoDetailResponse>({
    queryKey: motivoTrasladoKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return motivoTrasladoAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
