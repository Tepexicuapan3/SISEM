import { useMutation, useQueryClient } from "@tanstack/react-query";
import { physicalExamAPI } from "@api/resources/unified-history.api";
import type { SavePhysicalExamRequest } from "@api/types";
import { physicalExamKeys } from "@features/consulta-medica/modules/atencion/queries/usePhysicalExam";

export const useSavePhysicalExam = (visitId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SavePhysicalExamRequest) => physicalExamAPI.save(visitId, data),
    onSuccess: (saved) => {
      queryClient.setQueryData(physicalExamKeys.detail(visitId), saved);
    },
  });
};
