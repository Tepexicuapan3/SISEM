import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoServicioAmbulanciaAPI } from "@api/resources/catalogos/tipos-servicio-ambulancia.api";
import { tipoServicioAmbulanciaKeys } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/tipos-servicio-ambulancia.keys";

interface DeleteTipoServicioAmbulanciaPayload {
  id: number;
}

export const useDeleteTipoServicioAmbulancia = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteTipoServicioAmbulanciaPayload) => tipoServicioAmbulanciaAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: tipoServicioAmbulanciaKeys.list() });
      queryClient.removeQueries({ queryKey: tipoServicioAmbulanciaKeys.detail(variables.id) });
    },
  });
};
