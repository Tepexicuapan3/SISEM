import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cie9McAPI } from "@api/resources/catalogos/cie9-mc.api";
import type { CreateCie9McRequest, CreateCie9McResponse } from "@api/types";
import { cie9McKeys } from "@features/admin/modules/catalogos/cie9-mc/queries/cie9-mc.keys";

interface Payload {
  data: CreateCie9McRequest;
}

export const useCreateCie9Mc = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateCie9McResponse, Error, Payload>({
    mutationFn: ({ data }) => cie9McAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: cie9McKeys.all });
    },
  });
};
