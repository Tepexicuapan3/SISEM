import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoBajaPadronAPI } from "@api/resources/catalogos/motivos-baja-padron.api";
import type { UpdateMotivoBajaPadronRequest, UpdateMotivoBajaPadronResponse } from "@api/types";
import { motivoBajaPadronKeys } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/motivos-baja-padron.keys";

interface Payload {
  id: number;
  data: UpdateMotivoBajaPadronRequest;
}

export const useUpdateMotivoBajaPadron = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateMotivoBajaPadronResponse, Error, Payload>({
    mutationFn: ({ id, data }) => motivoBajaPadronAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(motivoBajaPadronKeys.detail(variables.id), {
        motivoBajaPadron: response.motivoBajaPadron,
      });
      void queryClient.invalidateQueries({ queryKey: motivoBajaPadronKeys.all });
    },
  });
};
