import { useMutation, useQueryClient } from "@tanstack/react-query";
import { bloodTypeAPI } from "@api/resources/unified-history.api";
import type { SaveBloodTypeRequest } from "@api/types";
import { unifiedHistoryKeys } from "@features/expedientes/queries/useUnifiedHistory";

interface Payload {
  noExp: string;
  pkNum: number;
  data: SaveBloodTypeRequest;
}

export const useSaveBloodType = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, data }: Payload) => bloodTypeAPI.save(noExp, pkNum, data),
    onSuccess: (saved, variables) => {
      // La respuesta ya trae vigente + historial: se escribe directo en cache.
      queryClient.setQueryData(unifiedHistoryKeys.bloodType(variables.noExp, variables.pkNum), saved);
    },
  });
};
