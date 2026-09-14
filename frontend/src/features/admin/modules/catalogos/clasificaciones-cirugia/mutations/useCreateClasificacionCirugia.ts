import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clasificacionCirugiaAPI } from "@api/resources/catalogos/clasificaciones-cirugia.api";
import type { CreateClasificacionCirugiaRequest, CreateClasificacionCirugiaResponse } from "@api/types";
import { clasificacionCirugiaKeys } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/clasificaciones-cirugia.keys";

interface Payload {
  data: CreateClasificacionCirugiaRequest;
}

export const useCreateClasificacionCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateClasificacionCirugiaResponse, Error, Payload>({
    mutationFn: ({ data }) => clasificacionCirugiaAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: clasificacionCirugiaKeys.all });
    },
  });
};
