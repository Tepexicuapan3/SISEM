import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ambulanciasAPI } from "@api/resources/ambulancias.api";
import type { CreateAmbulanceRequestRequest } from "@api/types";

export function useCreateAmbulanceRequest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAmbulanceRequestRequest) => ambulanciasAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ambulancias", "list"] });
    },
  });
}
