import { useQuery } from "@tanstack/react-query";
import { authorizerDesignationsAPI } from "@api/resources/catalogos/authorizer-designations.api";
import type { DesignacionDetailResponse } from "@api/types";
import { designacionKeys } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/designacion.keys";

export const useDesignacionDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<DesignacionDetailResponse>({
    queryKey: designacionKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return authorizerDesignationsAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
