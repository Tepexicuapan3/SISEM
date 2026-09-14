import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoTrasladoAPI } from "@api/resources/catalogos/motivos-traslado.api";
import { motivoTrasladoKeys } from "@features/admin/modules/catalogos/motivos-traslado/queries/motivos-traslado.keys";

interface DeleteMotivoTrasladoPayload {
  id: number;
}

export const useDeleteMotivoTraslado = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteMotivoTrasladoPayload) => motivoTrasladoAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: motivoTrasladoKeys.list() });
      queryClient.removeQueries({ queryKey: motivoTrasladoKeys.detail(variables.id) });
    },
  });
};
