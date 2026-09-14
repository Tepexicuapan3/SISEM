import { useMutation, useQueryClient } from "@tanstack/react-query";
import { destinoAmbulanciaAPI } from "@api/resources/catalogos/destinos-ambulancia.api";
import type { UpdateDestinoAmbulanciaRequest, UpdateDestinoAmbulanciaResponse } from "@api/types";
import { destinoAmbulanciaKeys } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/destinos-ambulancia.keys";

interface Payload {
  id: number;
  data: UpdateDestinoAmbulanciaRequest;
}

export const useUpdateDestinoAmbulancia = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateDestinoAmbulanciaResponse, Error, Payload>({
    mutationFn: ({ id, data }) => destinoAmbulanciaAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(destinoAmbulanciaKeys.detail(variables.id), {
        destinoAmbulancia: response.destinoAmbulancia,
      });
      void queryClient.invalidateQueries({ queryKey: destinoAmbulanciaKeys.all });
    },
  });
};
