import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cie9McAPI } from "@api/resources/catalogos/cie9-mc.api";
import type { UpdateCie9McRequest, UpdateCie9McResponse } from "@api/types";
import { cie9McKeys } from "@features/admin/modules/catalogos/cie9-mc/queries/cie9-mc.keys";

interface Payload {
  id: number;
  data: UpdateCie9McRequest;
}

export const useUpdateCie9Mc = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateCie9McResponse, Error, Payload>({
    mutationFn: ({ id, data }) => cie9McAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(cie9McKeys.detail(variables.id), {
        cie9Mc: response.cie9Mc,
      });
      void queryClient.invalidateQueries({ queryKey: cie9McKeys.all });
    },
  });
};
