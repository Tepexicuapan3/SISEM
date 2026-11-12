import { useMutation, useQueryClient } from "@tanstack/react-query";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import { medicamentosKeys } from "@features/admin/modules/catalogos/medicamentos/queries/medicamentos.keys";

interface DeleteMedicamentoPayload {
  id: number;
}

export const useDeleteMedicamento = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id }: DeleteMedicamentoPayload) => medicamentosAPI.delete(id),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: medicamentosKeys.list() });
      queryClient.removeQueries({
        queryKey: medicamentosKeys.detail(variables.id),
      });
    },
  });
};
