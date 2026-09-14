import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoTrasladoAPI } from "@api/resources/catalogos/motivos-traslado.api";
import type { CreateMotivoTrasladoRequest, CreateMotivoTrasladoResponse } from "@api/types";
import { motivoTrasladoKeys } from "@features/admin/modules/catalogos/motivos-traslado/queries/motivos-traslado.keys";

interface Payload {
  data: CreateMotivoTrasladoRequest;
}

export const useCreateMotivoTraslado = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateMotivoTrasladoResponse, Error, Payload>({
    mutationFn: ({ data }) => motivoTrasladoAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: motivoTrasladoKeys.all });
    },
  });
};
