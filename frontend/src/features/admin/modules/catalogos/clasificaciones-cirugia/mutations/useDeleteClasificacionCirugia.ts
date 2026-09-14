import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clasificacionCirugiaAPI } from "@api/resources/catalogos/clasificaciones-cirugia.api";
import { clasificacionCirugiaKeys } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/clasificaciones-cirugia.keys";

interface DeleteClasificacionCirugiaPayload {
  id: number;
}

export const useDeleteClasificacionCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteClasificacionCirugiaPayload) => clasificacionCirugiaAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: clasificacionCirugiaKeys.list() });
      queryClient.removeQueries({ queryKey: clasificacionCirugiaKeys.detail(variables.id) });
    },
  });
};
