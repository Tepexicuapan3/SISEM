import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoCancelacionNotaAPI } from "@api/resources/catalogos/motivos-cancelacion-nota.api";
import type { UpdateMotivoCancelacionNotaRequest, UpdateMotivoCancelacionNotaResponse } from "@api/types";
import { motivoCancelacionNotaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/motivos-cancelacion-nota.keys";

interface Payload {
  id: number;
  data: UpdateMotivoCancelacionNotaRequest;
}

export const useUpdateMotivoCancelacionNota = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateMotivoCancelacionNotaResponse, Error, Payload>({
    mutationFn: ({ id, data }) => motivoCancelacionNotaAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(motivoCancelacionNotaKeys.detail(variables.id), {
        motivoCancelacionNota: response.motivoCancelacionNota,
      });
      void queryClient.invalidateQueries({ queryKey: motivoCancelacionNotaKeys.all });
    },
  });
};
