import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cie9McAPI } from "@api/resources/catalogos/cie9-mc.api";
import { cie9McKeys } from "@features/admin/modules/catalogos/cie9-mc/queries/cie9-mc.keys";

interface DeleteCie9McPayload {
  id: number;
}

export const useDeleteCie9Mc = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteCie9McPayload) => cie9McAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: cie9McKeys.list() });
      queryClient.removeQueries({
        queryKey: cie9McKeys.detail(variables.id),
      });
    },
  });
};
