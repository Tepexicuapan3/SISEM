import { useQuery } from "@tanstack/react-query";
import { motivoCancelacionCirugiaAPI } from "@api/resources/catalogos/motivos-cancelacion-cirugia.api";
import type { MotivoCancelacionCirugiaDetailResponse } from "@api/types";
import { motivoCancelacionCirugiaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/motivos-cancelacion-cirugia.keys";

export const useMotivoCancelacionCirugiaDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<MotivoCancelacionCirugiaDetailResponse>({
    queryKey: motivoCancelacionCirugiaKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return motivoCancelacionCirugiaAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
