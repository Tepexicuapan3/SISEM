import { useMutation, useQueryClient } from "@tanstack/react-query";
import { visitsAPI } from "@api/resources/visits.api";
import type { CloseVisitRequest } from "@api/types";
import { visitFlowKeys } from "@realtime/visits/query-keys";
import { DOCTOR_ATTENDED_TODAY_KEY } from "@features/consulta-medica/modules/atencion/queries/useDoctorAttendedToday";

interface CloseVisitInput {
  visitId: number;
  data: CloseVisitRequest;
}

export const useCloseVisit = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ visitId, data }: CloseVisitInput) =>
      visitsAPI.closeVisit(visitId, data),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: visitFlowKeys.lists() }),
        queryClient.invalidateQueries({ queryKey: DOCTOR_ATTENDED_TODAY_KEY }),
      ]);
    },
  });
};
