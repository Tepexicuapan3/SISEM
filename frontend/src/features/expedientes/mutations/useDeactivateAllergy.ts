import { useMutation, useQueryClient } from "@tanstack/react-query";
import { allergyAPI } from "@api/resources/allergy.api";
import { allergyKeys } from "@features/expedientes/queries/useAllergies";

interface Payload {
  noExp: string;
  pkNum: number;
  allergyId: number;
}

export const useDeactivateAllergy = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, allergyId }: Payload) =>
      allergyAPI.deactivate(noExp, pkNum, allergyId),
    onSuccess: (_deactivated, variables) => {
      queryClient.invalidateQueries({
        queryKey: allergyKeys.list(variables.noExp, variables.pkNum),
      });
    },
  });
};
