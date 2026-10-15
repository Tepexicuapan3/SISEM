import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authorizerDesignationsAPI } from "@api/resources/catalogos/authorizer-designations.api";
import type { DesignacionDetailResponse, DesignacionWriteRequest } from "@api/types";
import { designacionKeys } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/designacion.keys";

interface Payload {
  data: DesignacionWriteRequest;
}

export const useCreateDesignacion = () => {
  const queryClient = useQueryClient();

  return useMutation<DesignacionDetailResponse, Error, Payload>({
    mutationFn: ({ data }) => authorizerDesignationsAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: designacionKeys.all });
    },
  });
};
