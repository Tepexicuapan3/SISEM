import { useMutation, useQueryClient } from "@tanstack/react-query";
import { destinoAmbulanciaAPI } from "@api/resources/catalogos/destinos-ambulancia.api";
import { destinoAmbulanciaKeys } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/destinos-ambulancia.keys";

interface DeleteDestinoAmbulanciaPayload {
  id: number;
}

export const useDeleteDestinoAmbulancia = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteDestinoAmbulanciaPayload) => destinoAmbulanciaAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: destinoAmbulanciaKeys.list() });
      queryClient.removeQueries({ queryKey: destinoAmbulanciaKeys.detail(variables.id) });
    },
  });
};
