import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoBajaPadronAPI } from "@api/resources/catalogos/motivos-baja-padron.api";
import type { CreateMotivoBajaPadronRequest, CreateMotivoBajaPadronResponse } from "@api/types";
import { motivoBajaPadronKeys } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/motivos-baja-padron.keys";

interface Payload {
  data: CreateMotivoBajaPadronRequest;
}

export const useCreateMotivoBajaPadron = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateMotivoBajaPadronResponse, Error, Payload>({
    mutationFn: ({ data }) => motivoBajaPadronAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: motivoBajaPadronKeys.all });
    },
  });
};
