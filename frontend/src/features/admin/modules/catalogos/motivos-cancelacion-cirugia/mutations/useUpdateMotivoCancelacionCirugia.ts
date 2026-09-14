import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoCancelacionCirugiaAPI } from "@api/resources/catalogos/motivos-cancelacion-cirugia.api";
import type { UpdateMotivoCancelacionCirugiaRequest, UpdateMotivoCancelacionCirugiaResponse } from "@api/types";
import { motivoCancelacionCirugiaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/motivos-cancelacion-cirugia.keys";

interface Payload {
  id: number;
  data: UpdateMotivoCancelacionCirugiaRequest;
}

export const useUpdateMotivoCancelacionCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateMotivoCancelacionCirugiaResponse, Error, Payload>({
    mutationFn: ({ id, data }) => motivoCancelacionCirugiaAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(motivoCancelacionCirugiaKeys.detail(variables.id), {
        motivoCancelacionCirugia: response.motivoCancelacionCirugia,
      });
      void queryClient.invalidateQueries({ queryKey: motivoCancelacionCirugiaKeys.all });
    },
  });
};
