import { useMutation, useQueryClient } from "@tanstack/react-query";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import type { CreateMedicamentoRequest, CreateMedicamentoResponse } from "@api/types";
import { medicamentosKeys } from "@features/admin/modules/catalogos/medicamentos/queries/medicamentos.keys";

interface Payload {
  data: CreateMedicamentoRequest;
}

export const useCreateMedicamento = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateMedicamentoResponse, Error, Payload>({
    mutationFn: ({ data }) => medicamentosAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: medicamentosKeys.all });
    },
  });
};
