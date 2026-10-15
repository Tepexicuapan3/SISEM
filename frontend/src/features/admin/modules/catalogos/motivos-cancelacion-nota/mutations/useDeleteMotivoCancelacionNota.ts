import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoCancelacionNotaAPI } from "@api/resources/catalogos/motivos-cancelacion-nota.api";
import { motivoCancelacionNotaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/motivos-cancelacion-nota.keys";

interface DeleteMotivoCancelacionNotaPayload {
  id: number;
}

export const useDeleteMotivoCancelacionNota = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteMotivoCancelacionNotaPayload) => motivoCancelacionNotaAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: motivoCancelacionNotaKeys.list() });
      queryClient.removeQueries({ queryKey: motivoCancelacionNotaKeys.detail(variables.id) });
    },
  });
};
