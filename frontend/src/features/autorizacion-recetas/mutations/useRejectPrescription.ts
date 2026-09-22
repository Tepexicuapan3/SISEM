import { useMutation, useQueryClient } from "@tanstack/react-query";
import { prescriptionAuthorizationsAPI } from "@api/resources/prescription-authorizations.api";
import type { RejectPrescriptionRequest } from "@api/types";

export function useRejectPrescription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      prescriptionAuthorizationsAPI.reject(id, { reason } satisfies RejectPrescriptionRequest),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["prescription-authorizations"] });
    },
  });
}
