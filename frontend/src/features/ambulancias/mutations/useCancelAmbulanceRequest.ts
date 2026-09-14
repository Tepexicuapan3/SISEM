import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ambulanciasAPI } from "@api/resources/ambulancias.api";

export function useCancelAmbulanceRequest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => ambulanciasAPI.cancel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ambulancias", "list"] });
    },
  });
}
