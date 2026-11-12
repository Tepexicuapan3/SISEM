import { useQuery } from "@tanstack/react-query";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import type { MedicamentoDetailResponse } from "@api/types";
import { medicamentosKeys } from "@features/admin/modules/catalogos/medicamentos/queries/medicamentos.keys";

export const useMedicamentoDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<MedicamentoDetailResponse>({
    queryKey: medicamentosKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return medicamentosAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
