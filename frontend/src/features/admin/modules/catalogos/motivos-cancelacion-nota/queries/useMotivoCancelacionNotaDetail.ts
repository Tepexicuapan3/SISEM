import { useQuery } from "@tanstack/react-query";
import { motivoCancelacionNotaAPI } from "@api/resources/catalogos/motivos-cancelacion-nota.api";
import type { MotivoCancelacionNotaDetailResponse } from "@api/types";
import { motivoCancelacionNotaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/motivos-cancelacion-nota.keys";

export const useMotivoCancelacionNotaDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<MotivoCancelacionNotaDetailResponse>({
    queryKey: motivoCancelacionNotaKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return motivoCancelacionNotaAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
