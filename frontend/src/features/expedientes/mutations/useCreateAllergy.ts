import { useMutation, useQueryClient } from "@tanstack/react-query";
import { allergyAPI } from "@api/resources/allergy.api";
import type { CreateAllergyRequest } from "@api/types";
import { allergyKeys } from "@features/expedientes/queries/useAllergies";

interface Payload {
  noExp: string;
  pkNum: number;
  data: CreateAllergyRequest;
}

export const useCreateAllergy = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, data }: Payload) =>
      allergyAPI.create(noExp, pkNum, data),
    onSuccess: (_created, variables) => {
      queryClient.invalidateQueries({
        queryKey: allergyKeys.list(variables.noExp, variables.pkNum),
      });
    },
  });
};
