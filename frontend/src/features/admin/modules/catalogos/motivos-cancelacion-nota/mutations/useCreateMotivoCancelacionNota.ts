import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoCancelacionNotaAPI } from "@api/resources/catalogos/motivos-cancelacion-nota.api";
import type { CreateMotivoCancelacionNotaRequest, CreateMotivoCancelacionNotaResponse } from "@api/types";
import { motivoCancelacionNotaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/motivos-cancelacion-nota.keys";

interface Payload {
  data: CreateMotivoCancelacionNotaRequest;
}

export const useCreateMotivoCancelacionNota = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateMotivoCancelacionNotaResponse, Error, Payload>({
    mutationFn: ({ data }) => motivoCancelacionNotaAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: motivoCancelacionNotaKeys.all });
    },
  });
};
