import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authorizerDesignationsAPI } from "@api/resources/catalogos/authorizer-designations.api";
import type { DesignacionDetailResponse, DesignacionWriteRequest } from "@api/types";
import { designacionKeys } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/designacion.keys";

interface Payload {
  id: number;
  data: DesignacionWriteRequest;
}

export const useUpdateDesignacion = () => {
  const queryClient = useQueryClient();

  return useMutation<DesignacionDetailResponse, Error, Payload>({
    mutationFn: ({ id, data }) => authorizerDesignationsAPI.update(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: designacionKeys.all });
    },
  });
};
