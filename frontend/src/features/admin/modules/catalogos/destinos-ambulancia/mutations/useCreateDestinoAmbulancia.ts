import { useMutation, useQueryClient } from "@tanstack/react-query";
import { destinoAmbulanciaAPI } from "@api/resources/catalogos/destinos-ambulancia.api";
import type { CreateDestinoAmbulanciaRequest, CreateDestinoAmbulanciaResponse } from "@api/types";
import { destinoAmbulanciaKeys } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/destinos-ambulancia.keys";

interface Payload {
  data: CreateDestinoAmbulanciaRequest;
}

export const useCreateDestinoAmbulancia = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateDestinoAmbulanciaResponse, Error, Payload>({
    mutationFn: ({ data }) => destinoAmbulanciaAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: destinoAmbulanciaKeys.all });
    },
  });
};
