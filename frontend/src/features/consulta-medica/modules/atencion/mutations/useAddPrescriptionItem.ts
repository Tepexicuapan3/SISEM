import { useMutation, useQueryClient } from "@tanstack/react-query";
import { visitsAPI } from "@api/resources/visits.api";
import type { AddPrescriptionItemRequest } from "@api/types";

interface AddPrescriptionItemInput {
  visitId: number;
  data: AddPrescriptionItemRequest;
}

export const useAddPrescriptionItem = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ visitId, data }: AddPrescriptionItemInput) =>
      visitsAPI.addPrescriptionItem(visitId, data),
    onSuccess: async (result, { visitId }) => {
      // Si el backend respondio con `requiresAcknowledgment`, NO se creo
      // ningun item -- no hay nada que invalidar todavia.
      if ("requiresAcknowledgment" in result) return;
      await queryClient.invalidateQueries({
        queryKey: ["doctor-consultation", "prescription-items", visitId],
      });
    },
  });
};
