import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoCirugiaAPI } from "@api/resources/catalogos/tipos-cirugia.api";
import type { CreateTipoCirugiaRequest, CreateTipoCirugiaResponse } from "@api/types";
import { tipoCirugiaKeys } from "@features/admin/modules/catalogos/tipos-cirugia/queries/tipos-cirugia.keys";

interface Payload {
  data: CreateTipoCirugiaRequest;
}

export const useCreateTipoCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateTipoCirugiaResponse, Error, Payload>({
    mutationFn: ({ data }) => tipoCirugiaAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tipoCirugiaKeys.all });
    },
  });
};
