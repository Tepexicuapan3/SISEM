import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clasificacionCirugiaAPI } from "@api/resources/catalogos/clasificaciones-cirugia.api";
import type { UpdateClasificacionCirugiaRequest, UpdateClasificacionCirugiaResponse } from "@api/types";
import { clasificacionCirugiaKeys } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/clasificaciones-cirugia.keys";

interface Payload {
  id: number;
  data: UpdateClasificacionCirugiaRequest;
}

export const useUpdateClasificacionCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateClasificacionCirugiaResponse, Error, Payload>({
    mutationFn: ({ id, data }) => clasificacionCirugiaAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(clasificacionCirugiaKeys.detail(variables.id), {
        clasificacionCirugia: response.clasificacionCirugia,
      });
      void queryClient.invalidateQueries({ queryKey: clasificacionCirugiaKeys.all });
    },
  });
};
