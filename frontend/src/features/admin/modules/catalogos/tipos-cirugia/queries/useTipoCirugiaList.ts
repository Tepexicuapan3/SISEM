import { tipoCirugiaAPI } from "@api/resources/catalogos/tipos-cirugia.api";
import type { TipoCirugiaListParams, TipoCirugiaListResponse } from "@api/types";
import { tipoCirugiaKeys } from "@features/admin/modules/catalogos/tipos-cirugia/queries/tipos-cirugia.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useTipoCirugiaList = createCatalogListHook<
  TipoCirugiaListParams,
  TipoCirugiaListResponse
>({
  keys: tipoCirugiaKeys,
  getAll: tipoCirugiaAPI.getAll,
});
