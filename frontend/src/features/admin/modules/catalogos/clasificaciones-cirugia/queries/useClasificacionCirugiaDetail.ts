import { useQuery } from "@tanstack/react-query";
import { clasificacionCirugiaAPI } from "@api/resources/catalogos/clasificaciones-cirugia.api";
import type { ClasificacionCirugiaDetailResponse } from "@api/types";
import { clasificacionCirugiaKeys } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/clasificaciones-cirugia.keys";

export const useClasificacionCirugiaDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<ClasificacionCirugiaDetailResponse>({
    queryKey: clasificacionCirugiaKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return clasificacionCirugiaAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
