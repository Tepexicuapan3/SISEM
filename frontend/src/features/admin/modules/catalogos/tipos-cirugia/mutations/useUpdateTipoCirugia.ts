import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoCirugiaAPI } from "@api/resources/catalogos/tipos-cirugia.api";
import type { UpdateTipoCirugiaRequest, UpdateTipoCirugiaResponse } from "@api/types";
import { tipoCirugiaKeys } from "@features/admin/modules/catalogos/tipos-cirugia/queries/tipos-cirugia.keys";

interface Payload {
  id: number;
  data: UpdateTipoCirugiaRequest;
}

export const useUpdateTipoCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateTipoCirugiaResponse, Error, Payload>({
    mutationFn: ({ id, data }) => tipoCirugiaAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(tipoCirugiaKeys.detail(variables.id), {
        tipoCirugia: response.tipoCirugia,
      });
      void queryClient.invalidateQueries({ queryKey: tipoCirugiaKeys.all });
    },
  });
};
