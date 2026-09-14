import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoCancelacionCirugiaAPI } from "@api/resources/catalogos/motivos-cancelacion-cirugia.api";
import type { CreateMotivoCancelacionCirugiaRequest, CreateMotivoCancelacionCirugiaResponse } from "@api/types";
import { motivoCancelacionCirugiaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/motivos-cancelacion-cirugia.keys";

interface Payload {
  data: CreateMotivoCancelacionCirugiaRequest;
}

export const useCreateMotivoCancelacionCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateMotivoCancelacionCirugiaResponse, Error, Payload>({
    mutationFn: ({ data }) => motivoCancelacionCirugiaAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: motivoCancelacionCirugiaKeys.all });
    },
  });
};
