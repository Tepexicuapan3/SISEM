import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cirugiasAPI } from "@api/resources/cirugias.api";
import type { CancelSurgeryRequest } from "@api/types";

export function useCancelSurgery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CancelSurgeryRequest }) =>
      cirugiasAPI.cancel(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cirugias", "list"] });
    },
  });
}
