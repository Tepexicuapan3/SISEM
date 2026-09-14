import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoServicioAmbulanciaAPI } from "@api/resources/catalogos/tipos-servicio-ambulancia.api";
import type { CreateTipoServicioAmbulanciaRequest, CreateTipoServicioAmbulanciaResponse } from "@api/types";
import { tipoServicioAmbulanciaKeys } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/tipos-servicio-ambulancia.keys";

interface Payload {
  data: CreateTipoServicioAmbulanciaRequest;
}

export const useCreateTipoServicioAmbulancia = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateTipoServicioAmbulanciaResponse, Error, Payload>({
    mutationFn: ({ data }) => tipoServicioAmbulanciaAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tipoServicioAmbulanciaKeys.all });
    },
  });
};
