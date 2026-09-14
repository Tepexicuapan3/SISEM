import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motivoCancelacionCirugiaAPI } from "@api/resources/catalogos/motivos-cancelacion-cirugia.api";
import { motivoCancelacionCirugiaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/motivos-cancelacion-cirugia.keys";

interface DeleteMotivoCancelacionCirugiaPayload {
  id: number;
}

export const useDeleteMotivoCancelacionCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteMotivoCancelacionCirugiaPayload) => motivoCancelacionCirugiaAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: motivoCancelacionCirugiaKeys.list() });
      queryClient.removeQueries({ queryKey: motivoCancelacionCirugiaKeys.detail(variables.id) });
    },
  });
};
