import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cirugiasAPI } from "@api/resources/cirugias.api";
import type { ScheduleSurgeryRequest } from "@api/types";

export function useScheduleSurgery() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ScheduleSurgeryRequest) => cirugiasAPI.schedule(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cirugias", "list"] });
    },
  });
}
