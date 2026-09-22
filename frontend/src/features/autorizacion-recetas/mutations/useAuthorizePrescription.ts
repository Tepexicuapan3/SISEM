import { useMutation, useQueryClient } from "@tanstack/react-query";
import { prescriptionAuthorizationsAPI } from "@api/resources/prescription-authorizations.api";

export function useAuthorizePrescription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => prescriptionAuthorizationsAPI.authorize(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["prescription-authorizations"] });
    },
  });
}
