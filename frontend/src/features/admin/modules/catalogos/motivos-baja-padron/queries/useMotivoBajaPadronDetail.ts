import { useQuery } from "@tanstack/react-query";
import { motivoBajaPadronAPI } from "@api/resources/catalogos/motivos-baja-padron.api";
import type { MotivoBajaPadronDetailResponse } from "@api/types";
import { motivoBajaPadronKeys } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/motivos-baja-padron.keys";

export const useMotivoBajaPadronDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<MotivoBajaPadronDetailResponse>({
    queryKey: motivoBajaPadronKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return motivoBajaPadronAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
