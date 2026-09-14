import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ambulanciasAPI } from "@api/resources/ambulancias.api";
import type { AuthorizeAmbulanceRequestRequest } from "@api/types";

export function useAuthorizeAmbulanceRequest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: AuthorizeAmbulanceRequestRequest }) =>
      ambulanciasAPI.authorize(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ambulancias", "list"] });
    },
  });
}
