import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoBajaPadronAPI } from "@api/resources/catalogos/motivos-baja-padron.api";
import { motivoBajaPadronKeys } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/motivos-baja-padron.keys";

interface DeleteMotivoBajaPadronPayload {
  id: number;
}

export const useDeleteMotivoBajaPadron = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteMotivoBajaPadronPayload) => motivoBajaPadronAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: motivoBajaPadronKeys.list() });
      queryClient.removeQueries({ queryKey: motivoBajaPadronKeys.detail(variables.id) });
    },
  });
};
