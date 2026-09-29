import { useMutation, useQueryClient } from "@tanstack/react-query";
import { allergyAPI } from "@api/resources/allergy.api";
import type { ChangeAllergyStatusRequest } from "@api/types";
import { allergyKeys } from "@features/expedientes/queries/useAllergies";

interface Payload {
  noExp: string;
  pkNum: number;
  allergyId: number;
  data: ChangeAllergyStatusRequest;
}

export const useChangeAllergyStatus = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, allergyId, data }: Payload) =>
      allergyAPI.changeStatus(noExp, pkNum, allergyId, data),
    onSuccess: (_updated, variables) => {
      queryClient.invalidateQueries({ queryKey: allergyKeys.list(variables.noExp, variables.pkNum) });
    },
  });
};
