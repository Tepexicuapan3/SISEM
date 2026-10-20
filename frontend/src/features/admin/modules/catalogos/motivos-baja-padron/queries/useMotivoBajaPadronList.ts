import { motivoBajaPadronAPI } from "@api/resources/catalogos/motivos-baja-padron.api";
import type { MotivoBajaPadronListParams, MotivoBajaPadronListResponse } from "@api/types";
import { motivoBajaPadronKeys } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/motivos-baja-padron.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useMotivoBajaPadronList = createCatalogListHook<
  MotivoBajaPadronListParams,
  MotivoBajaPadronListResponse
>({
  keys: motivoBajaPadronKeys,
  getAll: motivoBajaPadronAPI.getAll,
});
