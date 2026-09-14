import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoTrasladoAPI } from "@api/resources/catalogos/motivos-traslado.api";
import type { UpdateMotivoTrasladoRequest, UpdateMotivoTrasladoResponse } from "@api/types";
import { motivoTrasladoKeys } from "@features/admin/modules/catalogos/motivos-traslado/queries/motivos-traslado.keys";

interface Payload {
  id: number;
  data: UpdateMotivoTrasladoRequest;
}

export const useUpdateMotivoTraslado = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateMotivoTrasladoResponse, Error, Payload>({
    mutationFn: ({ id, data }) => motivoTrasladoAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(motivoTrasladoKeys.detail(variables.id), {
        motivoTraslado: response.motivoTraslado,
      });
      void queryClient.invalidateQueries({ queryKey: motivoTrasladoKeys.all });
    },
  });
};
