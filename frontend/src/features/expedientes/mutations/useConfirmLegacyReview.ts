import { useMutation, useQueryClient } from "@tanstack/react-query";
import { legacyConsultationAPI } from "@api/resources/legacy-consultation.api";
import type { ConfirmLegacyReviewRequest } from "@api/types/legacy-review.types";

interface Payload {
  noExp: string;
  pkNum: number;
  data: ConfirmLegacyReviewRequest;
}

export const useConfirmLegacyReview = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, data }: Payload) => legacyConsultationAPI.confirmReview(noExp, pkNum, data),
    onSuccess: () => {
      // Lo confirmado aparece en alergias, antecedentes y hábitos del expediente.
      queryClient.invalidateQueries({ queryKey: ["expedientes"] });
    },
  });
};
