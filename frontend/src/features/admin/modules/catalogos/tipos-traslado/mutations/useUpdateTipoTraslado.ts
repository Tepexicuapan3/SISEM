import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoTrasladoAPI } from "@api/resources/catalogos/tipos-traslado.api";
import type { UpdateTipoTrasladoRequest, UpdateTipoTrasladoResponse } from "@api/types";
import { tipoTrasladoKeys } from "@features/admin/modules/catalogos/tipos-traslado/queries/tipos-traslado.keys";

interface Payload {
  id: number;
  data: UpdateTipoTrasladoRequest;
}

export const useUpdateTipoTraslado = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateTipoTrasladoResponse, Error, Payload>({
    mutationFn: ({ id, data }) => tipoTrasladoAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(tipoTrasladoKeys.detail(variables.id), {
        tipoTraslado: response.tipoTraslado,
      });
      void queryClient.invalidateQueries({ queryKey: tipoTrasladoKeys.all });
    },
  });
};
