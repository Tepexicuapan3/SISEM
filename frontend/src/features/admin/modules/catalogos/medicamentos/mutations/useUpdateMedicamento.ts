import { useMutation, useQueryClient } from "@tanstack/react-query";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import type { UpdateMedicamentoRequest, UpdateMedicamentoResponse } from "@api/types";
import { medicamentosKeys } from "@features/admin/modules/catalogos/medicamentos/queries/medicamentos.keys";

interface Payload {
  id: number;
  data: UpdateMedicamentoRequest;
}

export const useUpdateMedicamento = () => {
  const queryClient = useQueryClient();

  return useMutation<UpdateMedicamentoResponse, Error, Payload>({
    mutationFn: ({ id, data }) => medicamentosAPI.update(id, data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(medicamentosKeys.detail(variables.id), {
        medication: response.medication,
      });
      void queryClient.invalidateQueries({ queryKey: medicamentosKeys.all });
    },
  });
};
