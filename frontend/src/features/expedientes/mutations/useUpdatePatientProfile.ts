import { useMutation, useQueryClient } from "@tanstack/react-query";
import { patientProfileAPI } from "@api/resources/clinical-history.api";
import type { UpdatePatientProfileRequest } from "@api/types";
import { clinicalHistoryKeys } from "@features/expedientes/queries/useClinicalHistory";

interface Payload {
  noExp: string;
  pkNum: number;
  data: UpdatePatientProfileRequest;
}

export const useUpdatePatientProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, data }: Payload) => patientProfileAPI.update(noExp, pkNum, data),
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(clinicalHistoryKeys.profile(variables.noExp, variables.pkNum), updated);
    },
  });
};
