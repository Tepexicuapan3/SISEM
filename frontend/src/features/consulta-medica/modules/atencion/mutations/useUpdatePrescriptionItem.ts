import { useMutation, useQueryClient } from "@tanstack/react-query";
import { visitsAPI } from "@api/resources/visits.api";
import type { UpdatePrescriptionItemRequest } from "@api/types";

interface UpdatePrescriptionItemInput {
  visitId: number;
  itemId: number;
  data: UpdatePrescriptionItemRequest;
}

export const useUpdatePrescriptionItem = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ visitId, itemId, data }: UpdatePrescriptionItemInput) =>
      visitsAPI.updatePrescriptionItem(visitId, itemId, data),
    onSuccess: async (_result, { visitId }) => {
      await queryClient.invalidateQueries({
        queryKey: ["doctor-consultation", "prescription-items", visitId],
      });
    },
  });
};
