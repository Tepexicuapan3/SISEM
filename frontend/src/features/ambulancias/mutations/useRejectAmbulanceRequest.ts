import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ambulanciasAPI } from "@api/resources/ambulancias.api";
import type { RejectAmbulanceRequestRequest } from "@api/types";

export function useRejectAmbulanceRequest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RejectAmbulanceRequestRequest }) =>
      ambulanciasAPI.reject(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ambulancias", "list"] });
    },
  });
}
