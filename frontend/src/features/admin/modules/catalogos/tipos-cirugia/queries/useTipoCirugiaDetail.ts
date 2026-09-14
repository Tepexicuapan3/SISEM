import { useQuery } from "@tanstack/react-query";
import { tipoCirugiaAPI } from "@api/resources/catalogos/tipos-cirugia.api";
import type { TipoCirugiaDetailResponse } from "@api/types";
import { tipoCirugiaKeys } from "@features/admin/modules/catalogos/tipos-cirugia/queries/tipos-cirugia.keys";

export const useTipoCirugiaDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<TipoCirugiaDetailResponse>({
    queryKey: tipoCirugiaKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return tipoCirugiaAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
