import { useMutation, useQueryClient } from "@tanstack/react-query";
import { odontogramAPI } from "@api/resources/odontogram.api";
import type { UpdateOdontogramToothRequest } from "@api/types";
import { odontogramKeys } from "@features/expedientes/queries/usePatientOdontogram";

interface Payload {
  noExp: string;
  pkNum: number;
  toothFdi: string;
  data: UpdateOdontogramToothRequest;
}

export const useUpdateOdontogramTooth = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noExp, pkNum, toothFdi, data }: Payload) =>
      odontogramAPI.updateTooth(noExp, pkNum, toothFdi, data),
    onSuccess: (_updated, variables) => {
      // Un cambio puede crear una VERSION nueva: se refrescan detalle y lista.
      void queryClient.invalidateQueries({
        queryKey: odontogramKeys.patient(variables.noExp, variables.pkNum),
      });
    },
  });
};
