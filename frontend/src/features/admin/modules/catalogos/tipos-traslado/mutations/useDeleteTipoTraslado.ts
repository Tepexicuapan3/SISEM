import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoTrasladoAPI } from "@api/resources/catalogos/tipos-traslado.api";
import { tipoTrasladoKeys } from "@features/admin/modules/catalogos/tipos-traslado/queries/tipos-traslado.keys";

interface DeleteTipoTrasladoPayload {
  id: number;
}

export const useDeleteTipoTraslado = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteTipoTrasladoPayload) => tipoTrasladoAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: tipoTrasladoKeys.list() });
      queryClient.removeQueries({ queryKey: tipoTrasladoKeys.detail(variables.id) });
    },
  });
};
