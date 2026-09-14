import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoServicioAmbulanciaAPI } from "@api/resources/catalogos/tipos-servicio-ambulancia.api";
import type { UpdateTipoServicioAmbulanciaRequest, UpdateTipoServicioAmbulanciaResponse } from "@api/types";
import { tipoServicioAmbulanciaKeys } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/tipos-servicio-ambulancia.keys";

interface Payload {
  id: number;
  data: UpdateTipoServicioAmbulanciaRequest;
}

export const useUpdateTipoServicioAmbulancia = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateTipoServicioAmbulanciaResponse, Error, Payload>({
    mutationFn: ({ id, data }) => tipoServicioAmbulanciaAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(tipoServicioAmbulanciaKeys.detail(variables.id), {
        tipoServicioAmbulancia: response.tipoServicioAmbulancia,
      });
      void queryClient.invalidateQueries({ queryKey: tipoServicioAmbulanciaKeys.all });
    },
  });
};
