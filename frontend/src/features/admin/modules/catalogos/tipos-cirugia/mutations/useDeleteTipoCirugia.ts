import { useMutation, useQueryClient } from "@tanstack/react-query";
import { tipoCirugiaAPI } from "@api/resources/catalogos/tipos-cirugia.api";
import { tipoCirugiaKeys } from "@features/admin/modules/catalogos/tipos-cirugia/queries/tipos-cirugia.keys";

interface DeleteTipoCirugiaPayload {
  id: number;
}

export const useDeleteTipoCirugia = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteTipoCirugiaPayload) => tipoCirugiaAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: tipoCirugiaKeys.list() });
      queryClient.removeQueries({ queryKey: tipoCirugiaKeys.detail(variables.id) });
    },
  });
};
