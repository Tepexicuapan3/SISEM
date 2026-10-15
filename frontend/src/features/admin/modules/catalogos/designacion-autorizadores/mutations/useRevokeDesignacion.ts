import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authorizerDesignationsAPI } from "@api/resources/catalogos/authorizer-designations.api";
import type { DeleteDesignacionResponse } from "@api/types";
import { designacionKeys } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/designacion.keys";

interface Payload {
  id: number;
}

export const useRevokeDesignacion = () => {
  const queryClient = useQueryClient();

  return useMutation<DeleteDesignacionResponse, Error, Payload>({
    mutationFn: ({ id }) => authorizerDesignationsAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: designacionKeys.all });
      queryClient.removeQueries({ queryKey: designacionKeys.detail(variables.id) });
    },
  });
};
