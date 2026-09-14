import { useMutation, useQueryClient } from "@tanstack/react-query";
import { consultationAddendumAPI } from "@api/resources/consultation-addendum.api";
import { consultationAddendaKeys } from "@features/expedientes/queries/useConsultationAddenda";

interface Payload {
  visitId: number;
  text: string;
}

export const useAddConsultationAddendum = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ visitId, text }: Payload) =>
      consultationAddendumAPI.add(visitId, { text }),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({
        queryKey: consultationAddendaKeys.list(variables.visitId),
      });
    },
  });
};
