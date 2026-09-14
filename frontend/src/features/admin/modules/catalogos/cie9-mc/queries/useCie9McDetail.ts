import { useQuery } from "@tanstack/react-query";
import { cie9McAPI } from "@api/resources/catalogos/cie9-mc.api";
import type { Cie9McDetailResponse } from "@api/types";
import { cie9McKeys } from "@features/admin/modules/catalogos/cie9-mc/queries/cie9-mc.keys";

export const useCie9McDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<Cie9McDetailResponse>({
    queryKey: cie9McKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return cie9McAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
