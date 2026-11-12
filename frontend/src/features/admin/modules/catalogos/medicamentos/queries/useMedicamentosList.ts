import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import type { MedicamentosListParams, MedicamentosListResponse } from "@api/types";
import { medicamentosKeys } from "@features/admin/modules/catalogos/medicamentos/queries/medicamentos.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useMedicamentosList = createCatalogListHook<
  MedicamentosListParams,
  MedicamentosListResponse
>({
  keys: medicamentosKeys,
  getAll: medicamentosAPI.getAll,
});
