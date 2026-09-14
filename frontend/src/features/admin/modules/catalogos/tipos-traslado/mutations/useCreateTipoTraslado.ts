import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoTrasladoAPI } from "@api/resources/catalogos/tipos-traslado.api";
import type { CreateTipoTrasladoRequest, CreateTipoTrasladoResponse } from "@api/types";
import { tipoTrasladoKeys } from "@features/admin/modules/catalogos/tipos-traslado/queries/tipos-traslado.keys";

interface Payload {
  data: CreateTipoTrasladoRequest;
}

export const useCreateTipoTraslado = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateTipoTrasladoResponse, Error, Payload>({
    mutationFn: ({ data }) => tipoTrasladoAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tipoTrasladoKeys.all });
    },
  });
};
